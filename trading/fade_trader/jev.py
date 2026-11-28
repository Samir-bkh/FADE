"""Le RÉFLEXE : schéma de décision Jev typé + client.

Jev (TypeSafe AI) prend un état texte + des questions typées et renvoie des
réponses typées avec probabilités. Trois primitives documentées par des
sources tierces : choice, score (<= 10 niveaux), noul (probabilité 0..1).

ATTENTION : le format exact de requête/réponse n'a pas pu être vérifié contre
docs.typesafe.ai depuis cet environnement (sources tierces divergentes sur
l'endpoint et l'ID de modèle). Tout ce qui dépend du format filaire est isolé
dans `TypeSafeWire` : à valider contre la doc officielle à la phase 2 du plan
avant toute mise en production. Le reste du système ne dépend que de
`JevDecision`.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Protocol

import httpx


# ------------------------------------------------------------------ schéma
@dataclass(frozen=True)
class Question:
    key: str
    kind: str                     # "choice" | "score" | "noul"
    prompt: str
    options: tuple[str, ...] = ()
    levels: int = 0               # pour score : 0..levels-1


@dataclass(frozen=True)
class JevSchema:
    version: str
    symbol: str
    thesis: str                   # contexte de la thèse (lent), inclus dans l'état
    horizon_min: int              # horizon de jugement de la direction
    reward_risk: float            # b du Kelly : take-profit / stop, fixé par le CODE
    stop_bps: float
    questions: tuple[Question, ...]

    @staticmethod
    def load(path: Path) -> "JevSchema":
        d = json.loads(Path(path).read_text())
        qs = tuple(Question(**{**q, "options": tuple(q.get("options", ()))}) for q in d.pop("questions"))
        return JevSchema(questions=qs, **d)

    def dump(self, path: Path) -> None:
        d = asdict(self)
        Path(path).write_text(json.dumps(d, indent=2, ensure_ascii=False))


def core_questions(thesis_hint: str) -> tuple[Question, ...]:
    """Les cinq questions imposées, évaluées en parallèle en un seul appel."""
    return (
        Question("regime", "choice",
                 "Quel est le régime de marché à court terme pour ce symbole, d'après l'état ?",
                 options=("trending", "mean_reverting", "high_vol", "crisis")),
        Question("direction", "choice",
                 f"Sur l'horizon indiqué, quelle position a l'espérance la plus favorable ? {thesis_hint}",
                 options=("long", "short", "neutral")),
        Question("toxic_flow", "noul",
                 "Le flux d'ordres récent est-il toxique (informé/adverse) pour un preneur de liquidité ?"),
        Question("setup_quality", "score",
                 "Qualité de la configuration : 0 = aucune, 1 = faible, 2 = bonne, 3 = excellente.",
                 levels=4),
        Question("risk_state", "choice",
                 "Compte tenu de la position, du drawdown et de la volatilité, quel état de risque ?",
                 options=("safe", "near_limit", "reduce")),
    )


# ------------------------------------------------------------------ décision
@dataclass(frozen=True)
class Choice:
    label: str
    probs: dict[str, float]
    confidence: float


@dataclass(frozen=True)
class JevDecision:
    regime: Choice
    direction: Choice
    toxic_flow: float
    setup_quality: int
    setup_probs: dict[str, float]
    risk_state: Choice
    latency_ms: float
    model: str = ""
    raw: dict = field(default_factory=dict, repr=False)


class DecisionError(RuntimeError):
    pass


def _validate_choice(name: str, c: Choice, options: tuple[str, ...]) -> None:
    if c.label not in options:
        raise DecisionError(f"{name}: label hors options {c.label!r}")
    s = sum(c.probs.values())
    if not (0.98 <= s <= 1.02) or any(p < 0 or p > 1 for p in c.probs.values()):
        raise DecisionError(f"{name}: distribution invalide (somme={s:.3f})")
    if not (0.0 <= c.confidence <= 1.0):
        raise DecisionError(f"{name}: confiance hors [0,1]")


def validate(dec: JevDecision, schema: JevSchema) -> JevDecision:
    """Validation stricte : toute anomalie -> exception -> HOLD dans la politique."""
    opts = {q.key: q.options for q in schema.questions if q.kind == "choice"}
    _validate_choice("regime", dec.regime, opts["regime"])
    _validate_choice("direction", dec.direction, opts["direction"])
    _validate_choice("risk_state", dec.risk_state, opts["risk_state"])
    if not (0.0 <= dec.toxic_flow <= 1.0):
        raise DecisionError("toxic_flow hors [0,1]")
    if dec.setup_quality not in (0, 1, 2, 3):
        raise DecisionError("setup_quality hors 0..3")
    return dec


# ------------------------------------------------------------------ transport
class Reflex(Protocol):
    def decide(self, schema: JevSchema, state_text: str) -> JevDecision: ...


class TypeSafeWire:
    """Format filaire. À VÉRIFIER contre docs.typesafe.ai (cf. en-tête)."""

    @staticmethod
    def build(schema: JevSchema, state_text: str, model: str) -> dict:
        qs = []
        for q in schema.questions:
            item: dict = {"name": q.key, "type": q.kind, "question": q.prompt}
            if q.kind == "choice":
                item["options"] = list(q.options)
            if q.kind == "score":
                item["levels"] = q.levels
            qs.append(item)
        state = f"[thesis] {schema.thesis}\n[horizon_min] {schema.horizon_min}\n[state]\n{state_text}"
        return {"model": model, "state": state, "questions": qs}

    @staticmethod
    def parse(body: dict, latency_ms: float) -> JevDecision:
        ans = body.get("answers") or body.get("results") or body
        if isinstance(ans, list):
            ans = {a.get("name"): a for a in ans}

        def choice(k: str) -> Choice:
            a = ans[k]
            probs = {str(o): float(p) for o, p in a["probabilities"].items()}
            label = a.get("answer") or a.get("selected") or max(probs, key=probs.get)
            conf = float(a.get("confidence", max(probs.values())))
            return Choice(str(label), probs, conf)

        tf = ans["toxic_flow"]
        tf_p = float(tf.get("probability", tf.get("value", tf.get("answer"))) if isinstance(tf, dict) else tf)
        sq = ans["setup_quality"]
        sq_probs = {str(k): float(v) for k, v in sq.get("probabilities", {}).items()}
        sq_val = sq.get("score", sq.get("answer"))
        if sq_val is None and sq_probs:
            sq_val = max(sq_probs, key=sq_probs.get)
        return JevDecision(
            regime=choice("regime"), direction=choice("direction"), toxic_flow=tf_p,
            setup_quality=int(sq_val), setup_probs=sq_probs, risk_state=choice("risk_state"),
            latency_ms=latency_ms, model=str(body.get("model", "")), raw=body,
        )


class JevClient:
    """Client HTTP synchrone avec budget de latence strict. Tout échec lève ;
    l'appelant traduit en HOLD. Pas de retry dans le chemin chaud : une
    décision en retard est une décision périmée."""

    def __init__(self, api_key: str, base_url: str = "https://api.typesafe.ai/v1/systemone",
                 model: str = "jev-latest", timeout_s: float = 0.5):
        if not api_key:
            raise ValueError("TYPESAFE_API_KEY manquante (clé issue de console.typesafe.ai)")
        self.url, self.model = base_url, model
        self._http = httpx.Client(timeout=timeout_s, headers={"Authorization": f"Bearer {api_key}"})

    def decide(self, schema: JevSchema, state_text: str) -> JevDecision:
        payload = TypeSafeWire.build(schema, state_text, self.model)
        t0 = time.perf_counter()
        r = self._http.post(self.url, json=payload)
        latency = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        return validate(TypeSafeWire.parse(r.json(), latency), schema)


class ScriptedReflex:
    """Réflexe de substitution déterministe pour tests et papier-trading hors
    ligne. Ce n'est PAS une stratégie : une simple règle de flux pour exercer
    la tuyauterie de bout en bout."""

    def decide(self, schema: JevSchema, state_text: str) -> JevDecision:
        kv = {}
        for tok in state_text.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                kv[k] = v

        def num(k: str) -> float:
            try:
                return float(kv.get(k, "0"))
            except ValueError:
                return 0.0

        flow, imb, rv, dd = num("flow_imb_5m"), num("imb_l5"), num("rv_1m_bps"), num("dd_pct")
        score = 0.6 * flow + 0.4 * imb
        p_long = min(0.97, max(0.03, 0.5 + score * 2.0))
        p_neu = 0.04
        probs = {"long": p_long * (1 - p_neu), "short": (1 - p_long) * (1 - p_neu), "neutral": p_neu}
        lab = max(probs, key=probs.get)
        regime = "crisis" if rv > 40 else "high_vol" if rv > 15 else "trending" if abs(score) > 0.3 else "mean_reverting"
        rp = {r: 0.02 for r in ("trending", "mean_reverting", "high_vol", "crisis")}
        rp[regime] = 0.94
        rs = "reduce" if dd > 10 else "near_limit" if dd > 6 else "safe"
        rsp = {r: 0.03 for r in ("safe", "near_limit", "reduce")}
        rsp[rs] = 0.94
        q = 3 if abs(score) > 0.6 else 2 if abs(score) > 0.35 else 1 if abs(score) > 0.15 else 0
        return JevDecision(
            regime=Choice(regime, rp, 0.94), direction=Choice(lab, probs, max(probs.values())),
            toxic_flow=0.2, setup_quality=q, setup_probs={str(q): 1.0}, risk_state=Choice(rs, rsp, 0.94),
            latency_ms=0.0, model="scripted",
        )
