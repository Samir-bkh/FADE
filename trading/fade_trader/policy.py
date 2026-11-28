"""Politique : le code décide, Jev juge.

Jev fournit des jugements probabilistes. Ce module applique les seuils, la
taille et les sorties. Rien ici n'est délégué au modèle.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

from .jev import JevDecision, JevSchema
from .state_engine import Snapshot
from .types import Action, Intent


@dataclass(frozen=True)
class PolicyConfig:
    min_setup_quality: int = 2
    min_direction_conf: float = 0.80          # seuil sur la confiance brute de Jev (strict >)
    escalate_below_conf: float = 0.60
    max_toxic_flow: float = 0.50
    kelly_mult: float = 0.25                  # plafond : quart de Kelly
    max_risk_per_trade: float = 0.005         # 0,5 % de l'équité au stop
    roundtrip_cost_bps: float = 12.0          # frais taker x2 + slippage estimé : À MESURER en papier
    crisis_reduce_frac: float = 0.5

    def __post_init__(self):
        if self.kelly_mult > 0.25:
            raise ValueError("kelly_mult plafonné à 0.25 (quart de Kelly)")
        if self.min_direction_conf < 0.80 or self.min_setup_quality < 2:
            raise ValueError("les seuils d'entrée ne peuvent pas être relâchés sous la spécification")


class Calibrator:
    """Transforme la confiance brute de Jev en probabilité de gain calibrée.

    Par défaut (aucune donnée) : rétrécissement vers 0,5 d'un facteur 0,5.
    HYPOTHÈSE prudente, pas une mesure : un modèle non calibré sur ce domaine
    est supposé sur-confiant. La revue de nuit remplace ceci par une courbe
    isotone ajustée sur les résultats réels (scores de Brier à l'appui).
    """

    def __init__(self, edges: list[float] | None = None, values: list[float] | None = None,
                 shrink: float = 0.5, n_obs: int = 0):
        self.edges, self.values, self.shrink, self.n_obs = edges or [], values or [], shrink, n_obs

    def __call__(self, conf: float) -> float:
        if self.edges and self.values:
            for e, v in zip(self.edges, self.values):
                if conf <= e:
                    return v
            return self.values[-1]
        return 0.5 + self.shrink * (conf - 0.5)

    def to_dict(self) -> dict:
        return {"edges": self.edges, "values": self.values, "shrink": self.shrink, "n_obs": self.n_obs}

    @staticmethod
    def load(path: Path) -> "Calibrator":
        p = Path(path)
        return Calibrator(**json.loads(p.read_text())) if p.exists() else Calibrator()


def kelly_risk_fraction(p: float, b: float, cost_r: float) -> float:
    """Kelly pour un pari gagnant W = b - cost_r (en R) avec proba p et perdant
    L = 1 + cost_r. Kelly classique : f* = p/L - q/W (f = fraction misée, perte
    = f*L). Retourne f* x L, c.-à-d. la fraction d'équité PERDUE si le stop est
    touché (coûts inclus) — pas le notionnel."""
    edge = p * (b - cost_r) - (1 - p) * (1 + cost_r)
    return max(0.0, edge / (b - cost_r)) if b > cost_r else 0.0


@dataclass
class PositionClock:
    entry_ms: int | None = None


class Policy:
    def __init__(self, cfg: PolicyConfig, calibrator: Calibrator):
        self.cfg, self.cal = cfg, calibrator

    def exits(self, snap: Snapshot, schema: JevSchema, clock: PositionClock) -> Intent | None:
        if snap.pos_frac == 0:
            return None
        if snap.upnl_bps <= -schema.stop_bps:
            return Intent(Action.FLATTEN, 0, 0, f"stop {snap.upnl_bps:.0f} bps")
        if snap.upnl_bps >= schema.reward_risk * schema.stop_bps:
            return Intent(Action.FLATTEN, 0, 0, f"objectif {snap.upnl_bps:.0f} bps")
        if clock.entry_ms is not None and snap.as_of_ms - clock.entry_ms >= schema.horizon_min * 60_000:
            return Intent(Action.FLATTEN, 0, 0, "stop temporel")
        return None

    def decide(self, dec: JevDecision | None, snap: Snapshot, schema: JevSchema,
               clock: PositionClock) -> Intent:
        c = self.cfg
        ex = self.exits(snap, schema, clock)
        if ex:
            return ex
        if dec is None:
            return Intent(Action.HOLD, 0, 0, "pas de décision Jev (erreur/timeout)")

        escalate, why = False, ""
        if dec.regime.label == "crisis":
            escalate, why = True, "régime crise"
        elif dec.direction.confidence < c.escalate_below_conf:
            escalate, why = True, f"confiance direction {dec.direction.confidence:.2f} < {c.escalate_below_conf}"

        if dec.risk_state.label == "reduce" and snap.pos_frac != 0:
            return Intent(Action.REDUCE, abs(snap.pos_frac) * 0.5, 0, "risk_state=reduce", escalate, why)
        if dec.regime.label == "crisis" and snap.pos_frac != 0:
            return Intent(Action.REDUCE, abs(snap.pos_frac) * (1 - c.crisis_reduce_frac), 0,
                          "crise : réduction déterministe", True, why)
        if escalate:
            return Intent(Action.HOLD, 0, 0, "escalade, pas d'entrée", True, why)

        # Filtres d'entrée (tous obligatoires)
        if dec.setup_quality < c.min_setup_quality:
            return Intent(Action.HOLD, 0, 0, f"setup_quality {dec.setup_quality} < {c.min_setup_quality}")
        if dec.direction.label == "neutral":
            return Intent(Action.HOLD, 0, 0, "direction neutre")
        if not dec.direction.confidence > c.min_direction_conf:
            return Intent(Action.HOLD, 0, 0, f"confiance {dec.direction.confidence:.2f} <= {c.min_direction_conf}")
        if dec.risk_state.label != "safe":
            return Intent(Action.HOLD, 0, 0, f"risk_state={dec.risk_state.label}")
        if dec.toxic_flow >= c.max_toxic_flow:
            return Intent(Action.HOLD, 0, 0, f"flux toxique p={dec.toxic_flow:.2f}")

        direction = 1 if dec.direction.label == "long" else -1
        if snap.pos_frac * direction > 0:
            return Intent(Action.HOLD, 0, direction, "déjà positionné dans ce sens")

        p = self.cal(dec.direction.confidence)
        cost_r = (c.roundtrip_cost_bps + snap.spread_bps) / schema.stop_bps
        f_star = kelly_risk_fraction(p, schema.reward_risk, cost_r)
        risk_frac = min(c.kelly_mult * f_star, c.max_risk_per_trade)
        if risk_frac <= 0:
            return Intent(Action.HOLD, 0, direction, f"pas d'avantage après coûts (p={p:.3f})",
                          kelly_raw=f_star, p_win=p)
        notional_frac = risk_frac / ((schema.stop_bps + c.roundtrip_cost_bps + snap.spread_bps) / 1e4)
        act = Action.BUY if direction > 0 else Action.SELL
        return Intent(act, notional_frac, direction, "entrée", kelly_raw=f_star, p_win=p)


def config_dict(cfg: PolicyConfig) -> dict:
    return asdict(cfg)
