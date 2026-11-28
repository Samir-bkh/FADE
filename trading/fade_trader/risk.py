"""Couche de risque déterministe et dure.

Règle absolue : aucune sortie de modèle (Jev ou Opus) n'entre dans ce module
autrement que comme une *demande* d'ordre. Les limites sont des constantes du
code ; la configuration ne peut que les resserrer, jamais les relâcher.

Ordre de vérification, avant CHAQUE ordre :
  1. kill switch (fichier + état mémoire)  -> si engagé : seuls les ordres reduce-only passent
  2. fraîcheur des données
  3. drawdown max (15 %)                   -> déclenche le kill switch + aplatissement
  4. perte quotidienne max                 -> déclenche le kill switch + aplatissement
  5. taille d'ordre max, position max, levier max
  6. cadence d'ordres
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, replace
from pathlib import Path

from .types import Order, Portfolio, RiskVerdict, Side


@dataclass(frozen=True)
class RiskLimits:
    max_drawdown_pct: float = 15.0
    max_daily_loss_pct: float = 3.0
    max_position_frac: float = 0.25       # |notional| / équité
    max_order_frac: float = 0.10          # notional d'un ordre / équité
    max_leverage: float = 1.0             # pas de levier par défaut
    max_book_age_ms: int = 2_000
    max_spread_bps: float = 25.0
    min_order_interval_ms: int = 5_000
    max_orders_per_day: int = 200


HARD_LIMITS = RiskLimits()


def tighten(base: RiskLimits, overrides: dict) -> RiskLimits:
    """Applique des surcharges uniquement si elles sont plus strictes."""
    stricter_is_lower = {
        "max_drawdown_pct", "max_daily_loss_pct", "max_position_frac", "max_order_frac",
        "max_leverage", "max_book_age_ms", "max_spread_bps", "max_orders_per_day",
    }
    stricter_is_higher = {"min_order_interval_ms"}
    kw = {}
    for k, v in overrides.items():
        cur = getattr(base, k)
        if k in stricter_is_lower:
            kw[k] = min(cur, type(cur)(v))
        elif k in stricter_is_higher:
            kw[k] = max(cur, type(cur)(v))
        else:
            raise KeyError(f"limite inconnue : {k}")
    return replace(base, **kw)


class KillSwitch:
    """Persisté sur disque pour survivre à un redémarrage. Un opérateur peut
    l'engager en créant le fichier (`touch state/KILL`) ; seul un opérateur
    peut le désengager (`fade-trader kill --release`)."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def engaged(self) -> bool:
        return self.path.exists()

    def engage(self, reason: str) -> None:
        if not self.path.exists():
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"reason": reason, "ts": time.time()}))
            os.replace(tmp, self.path)

    def reason(self) -> str:
        try:
            return json.loads(self.path.read_text()).get("reason", "manuel")
        except Exception:
            return "manuel"

    def release(self) -> None:
        self.path.unlink(missing_ok=True)


class RiskGate:
    def __init__(self, limits: RiskLimits, kill_switch: KillSwitch):
        self.limits = limits
        self.kill = kill_switch
        self._last_order_ms: int | None = None
        self._orders_today = 0
        self._day = ""

    # Appelé à chaque bloc, même sans ordre, pour déclencher les coupe-circuits.
    def update_breakers(self, pf: Portfolio, mark: float) -> str | None:
        eq = pf.equity(mark)
        pf.peak_equity = max(pf.peak_equity, eq)
        dd = 0.0 if pf.peak_equity <= 0 else (1 - eq / pf.peak_equity) * 100
        if dd >= self.limits.max_drawdown_pct:
            self.kill.engage(f"drawdown {dd:.2f}% >= {self.limits.max_drawdown_pct}%")
            return "drawdown"
        if pf.day_start_equity > 0:
            day_loss = (1 - eq / pf.day_start_equity) * 100
            if day_loss >= self.limits.max_daily_loss_pct:
                self.kill.engage(f"perte jour {day_loss:.2f}% >= {self.limits.max_daily_loss_pct}%")
                return "daily_loss"
        return None

    def check(self, order: Order, pf: Portfolio, mark: float, now_ms: int,
              book_age_ms: int, spread_bps: float, day_key: str) -> RiskVerdict:
        L = self.limits
        if day_key != self._day:
            self._day, self._orders_today = day_key, 0

        if order.qty <= 0 or not (mark > 0):
            return RiskVerdict(False, "quantité ou prix invalide")

        # Un ordre reduce-only ne doit jamais augmenter |position| ni la retourner.
        pos = pf.position_qty
        signed = order.qty if order.side is Side.BUY else -order.qty
        if order.reduce_only:
            if pos == 0 or (pos > 0) == (signed > 0):
                return RiskVerdict(False, "reduce-only sans position à réduire")
            qty = min(order.qty, abs(pos))
            # Les réductions passent même kill switch engagé et données périmées :
            # sortir du risque prime.
            return RiskVerdict(True, "réduction autorisée", qty=qty,
                               kill_switch_engaged=self.kill.engaged())

        # 1. kill switch
        if self.kill.engaged():
            return RiskVerdict(False, f"kill switch engagé : {self.kill.reason()}", kill_switch_engaged=True)
        # 2. fraîcheur / qualité du marché
        if book_age_ms > L.max_book_age_ms:
            return RiskVerdict(False, f"carnet périmé ({book_age_ms} ms)")
        if spread_bps > L.max_spread_bps:
            return RiskVerdict(False, f"spread trop large ({spread_bps:.1f} bps)")
        # 3-4. coupe-circuits
        tripped = self.update_breakers(pf, mark)
        if tripped:
            return RiskVerdict(False, f"coupe-circuit {tripped}", kill_switch_engaged=True)
        # 5. tailles
        eq = pf.equity(mark)
        if eq <= 0:
            return RiskVerdict(False, "équité nulle")
        max_order_qty = L.max_order_frac * eq / mark
        qty = min(order.qty, max_order_qty)
        new_pos = pos + (qty if order.side is Side.BUY else -qty)
        cap = min(L.max_position_frac, L.max_leverage) * eq / mark
        if abs(new_pos) > cap:
            room = max(0.0, cap - abs(pos)) if (pos >= 0) == (signed > 0) else cap + abs(pos)
            qty = min(qty, room)
        if qty * mark < 1e-9 or qty <= 0:
            return RiskVerdict(False, "position max atteinte")
        # 6. cadence
        if self._last_order_ms is not None and now_ms - self._last_order_ms < L.min_order_interval_ms:
            return RiskVerdict(False, "cadence d'ordres")
        if self._orders_today >= L.max_orders_per_day:
            return RiskVerdict(False, "quota d'ordres journalier")
        return RiskVerdict(True, "ok", qty=qty)

    def record_order(self, now_ms: int) -> None:
        self._last_order_ms = now_ms
        self._orders_today += 1
