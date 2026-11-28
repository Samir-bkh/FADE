"""Exécution. Seul le courtier papier est implémenté.

Le passage en réel exige d'écrire un adaptateur d'exchange (ccxt ou SDK natif)
qui respecte le protocole `Broker`, et de passer --live ET la variable
FADE_LIVE_ACK=je-comprends-le-risque. C'est une porte d'approbation opérateur,
volontairement non automatisable.
"""
from __future__ import annotations

import os
from typing import Protocol

from .types import BookLevel, Fill, Order, Portfolio, Side


class Broker(Protocol):
    def submit(self, order: Order, book_side: tuple[BookLevel, ...], ts_ms: int, pf: Portfolio) -> Fill | None: ...


class PaperBroker:
    """Ordre au marché simulé en balayant le carnet visible, plus un slippage
    additionnel prudent (le carnet visible sur-estime la liquidité réelle)."""

    def __init__(self, taker_fee_bps: float = 5.0, extra_slippage_bps: float = 2.0):
        self.fee_bps, self.slip_bps = taker_fee_bps, extra_slippage_bps

    def submit(self, order: Order, book_side: tuple[BookLevel, ...], ts_ms: int, pf: Portfolio) -> Fill | None:
        remaining, cost = order.qty, 0.0
        for lvl in book_side:
            take = min(remaining, lvl.size)
            cost += take * lvl.price
            remaining -= take
            if remaining <= 1e-12:
                break
        filled = order.qty - max(remaining, 0.0)
        if filled <= 0:
            return None
        px = cost / filled
        px *= 1 + (self.slip_bps / 1e4) * (1 if order.side is Side.BUY else -1)
        fee = filled * px * self.fee_bps / 1e4
        apply_fill(pf, order.side, filled, px, fee)
        return Fill(order, px, filled, fee, ts_ms)


def apply_fill(pf: Portfolio, side: Side, qty: float, px: float, fee: float) -> None:
    signed = qty if side is Side.BUY else -qty
    old = pf.position_qty
    new = old + signed
    if old == 0 or (old > 0) == (signed > 0):
        pf.avg_entry = (abs(old) * pf.avg_entry + qty * px) / abs(new) if new else 0.0
    else:
        closed = min(abs(signed), abs(old))
        pf.realized_pnl += closed * (px - pf.avg_entry) * (1 if old > 0 else -1)
        if abs(signed) > abs(old):
            pf.avg_entry = px
        elif new == 0:
            pf.avg_entry = 0.0
    pf.position_qty = new if abs(new) > 1e-12 else 0.0
    pf.cash -= signed * px + fee
    pf.fees_paid += fee


def assert_live_allowed() -> None:
    if os.environ.get("FADE_LIVE_ACK") != "je-comprends-le-risque":
        raise SystemExit("Mode réel refusé : FADE_LIVE_ACK absent. Porte opérateur.")
    raise SystemExit("Aucun adaptateur d'exchange réel n'est fourni. Phase 5 du plan.")
