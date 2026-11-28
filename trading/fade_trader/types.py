"""Types partagés. Tous les horodatages sont en millisecondes epoch UTC.

Convention causale : un événement n'est utilisable à l'instant `as_of_ms`
que si `ts_received_ms <= as_of_ms`. L'horodatage de réception (local) fait
foi, pas l'horodatage de l'exchange : c'est le moment où l'information a
réellement été disponible pour l'agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class Action(str, Enum):
    HOLD = "hold"
    BUY = "buy"
    SELL = "sell"
    REDUCE = "reduce"      # réduit la position existante vers zéro
    FLATTEN = "flatten"    # clôture totale


@dataclass(frozen=True)
class BookLevel:
    price: float
    size: float


@dataclass(frozen=True)
class OrderBook:
    symbol: str
    ts_exchange_ms: int
    ts_received_ms: int
    bids: tuple[BookLevel, ...]   # triés prix décroissant
    asks: tuple[BookLevel, ...]   # triés prix croissant

    def validate(self) -> None:
        if not self.bids or not self.asks:
            raise ValueError("carnet vide")
        if self.bids[0].price >= self.asks[0].price:
            raise ValueError("carnet croisé")
        if any(self.bids[i].price < self.bids[i + 1].price for i in range(len(self.bids) - 1)):
            raise ValueError("bids non triés")
        if any(self.asks[i].price > self.asks[i + 1].price for i in range(len(self.asks) - 1)):
            raise ValueError("asks non triés")


@dataclass(frozen=True)
class Trade:
    symbol: str
    ts_received_ms: int
    price: float
    size: float
    aggressor: Side


@dataclass(frozen=True)
class ContextPoint:
    """Donnée de contexte lente (funding, OI, ...) avec son instant de disponibilité."""
    name: str
    value: float
    ts_received_ms: int


@dataclass
class Portfolio:
    cash: float
    position_qty: float = 0.0
    avg_entry: float = 0.0
    peak_equity: float = 0.0
    day_start_equity: float = 0.0
    day_key: str = ""
    realized_pnl: float = 0.0
    fees_paid: float = 0.0

    def equity(self, mark: float) -> float:
        return self.cash + self.position_qty * mark


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    qty: float
    reduce_only: bool
    reason: str
    client_id: str


@dataclass(frozen=True)
class Fill:
    order: Order
    price: float
    qty: float
    fee: float
    ts_ms: int


@dataclass(frozen=True)
class Intent:
    action: Action
    target_frac: float          # fraction d'équité visée en valeur absolue (0..1)
    direction: int              # +1 long, -1 short, 0 aucune
    reason: str
    escalate: bool = False
    escalate_reason: str = ""
    kelly_raw: float = 0.0
    p_win: float = 0.0


@dataclass(frozen=True)
class RiskVerdict:
    allowed: bool
    reason: str
    qty: float = 0.0
    kill_switch_engaged: bool = False
    meta: dict = field(default_factory=dict)
