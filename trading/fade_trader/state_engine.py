"""Moteur d'état déterministe.

Transforme le flux brut (carnet, trades, contexte lent, portefeuille) en un
instantané numérique compact (< 400 tokens) à chaque bloc. Tout est calculé
ici, en code ; le modèle ne fait que lire l'instantané.

Garanties :
- Causalité stricte : seuls les événements avec ts_received_ms <= as_of_ms
  sont utilisés. Un événement daté du futur lève CausalityError plutôt que
  d'être silencieusement ignoré (une fuite du futur est un bug, pas un cas
  normal).
- Déterminisme : même entrée -> même sortie, octet pour octet (clé de hash
  dans le journal, reproductibilité de la revue de nuit).
"""
from __future__ import annotations

import hashlib
import math
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass

from .types import ContextPoint, OrderBook, Portfolio, Side, Trade

MAX_SNAPSHOT_TOKENS = 400


class CausalityError(RuntimeError):
    pass


def estimate_tokens(text: str) -> int:
    """Estimation conservatrice (sur-estime) : 1 token ~ 3 caractères pour du
    texte numérique dense. Le vrai compte dépend du tokenizer de Jev, que l'on
    ne connaît pas ; on prend une marge."""
    return math.ceil(len(text) / 3.0)


@dataclass(frozen=True)
class Snapshot:
    symbol: str
    as_of_ms: int
    book_age_ms: int
    mid: float
    spread_bps: float
    imb_l1: float          # (bid1 - ask1) / (bid1 + ask1), tailles
    imb_l5: float
    depth5_usd: float
    rv_1m_bps: float       # vol réalisée annualisée n'aurait pas de sens ici : écart-type des log-rendements 1s sur 60 s, en bps
    rv_15m_bps: float
    ret_5m_bps: float
    ret_1h_bps: float
    flow_imb_5m: float     # (achats agresseurs - ventes) / total, volume
    trades_5m: int
    funding_8h_bps: float | None
    oi_chg_1h_pct: float | None
    pos_frac: float        # notional position / équité, signé
    upnl_bps: float
    dd_pct: float          # drawdown depuis le pic d'équité
    day_pnl_pct: float

    def to_prompt(self) -> str:
        def f(x: float | None, nd: int = 2) -> str:
            return "na" if x is None else f"{x:.{nd}f}"

        lines = [
            f"sym={self.symbol} t={self.as_of_ms} book_age_ms={self.book_age_ms}",
            f"mid={self.mid:.6g} spread_bps={f(self.spread_bps)} depth5_usd={self.depth5_usd:.0f}",
            f"imb_l1={f(self.imb_l1, 3)} imb_l5={f(self.imb_l5, 3)} flow_imb_5m={f(self.flow_imb_5m, 3)} trades_5m={self.trades_5m}",
            f"rv_1m_bps={f(self.rv_1m_bps)} rv_15m_bps={f(self.rv_15m_bps)}",
            f"ret_5m_bps={f(self.ret_5m_bps)} ret_1h_bps={f(self.ret_1h_bps)}",
            f"funding_8h_bps={f(self.funding_8h_bps, 3)} oi_chg_1h_pct={f(self.oi_chg_1h_pct)}",
            f"pos_frac={f(self.pos_frac, 3)} upnl_bps={f(self.upnl_bps)} dd_pct={f(self.dd_pct)} day_pnl_pct={f(self.day_pnl_pct)}",
        ]
        return "\n".join(lines)

    def digest(self) -> str:
        return hashlib.sha256(self.to_prompt().encode()).hexdigest()[:16]


class StateEngine:
    """Un moteur par symbole. Alimenté par événements, interrogé par `snapshot(as_of)`."""

    def __init__(self, symbol: str, history_ms: int = 3_700_000):
        self.symbol = symbol
        self.history_ms = history_ms
        self._books: deque[OrderBook] = deque()
        self._book_ts: deque[int] = deque()
        self._trades: deque[Trade] = deque()
        self._context: dict[str, deque[ContextPoint]] = {}
        self._last_ingest_ms = 0

    # ---------------------------------------------------------------- ingestion
    def _check_monotonic(self, ts: int) -> None:
        if ts < self._last_ingest_ms:
            # Hors d'ordre : on refuse. Un réordonnancement silencieux pourrait
            # modifier rétroactivement des instantanés déjà journalisés.
            raise CausalityError(f"événement hors d'ordre ts={ts} < {self._last_ingest_ms}")
        self._last_ingest_ms = ts

    def on_book(self, book: OrderBook) -> None:
        if book.symbol != self.symbol:
            raise ValueError("symbole inattendu")
        book.validate()
        self._check_monotonic(book.ts_received_ms)
        self._books.append(book)
        self._book_ts.append(book.ts_received_ms)
        self._evict(book.ts_received_ms)

    def on_trade(self, trade: Trade) -> None:
        if trade.symbol != self.symbol:
            raise ValueError("symbole inattendu")
        self._check_monotonic(trade.ts_received_ms)
        self._trades.append(trade)

    def on_context(self, point: ContextPoint) -> None:
        self._check_monotonic(point.ts_received_ms)
        self._context.setdefault(point.name, deque(maxlen=512)).append(point)

    def _evict(self, now: int) -> None:
        horizon = now - self.history_ms
        while self._books and self._book_ts[0] < horizon:
            self._books.popleft()
            self._book_ts.popleft()
        while self._trades and self._trades[0].ts_received_ms < horizon:
            self._trades.popleft()

    # ---------------------------------------------------------------- requêtes
    def _book_at(self, t: int) -> OrderBook | None:
        i = bisect_right(self._book_ts, t)
        return self._books[i - 1] if i > 0 else None

    def _mid_at(self, t: int) -> float | None:
        b = self._book_at(t)
        return None if b is None else (b.bids[0].price + b.asks[0].price) / 2

    def _rv_bps(self, as_of: int, window_ms: int, step_ms: int = 1000) -> float:
        mids = []
        t = as_of - window_ms
        while t <= as_of:
            m = self._mid_at(t)
            if m is not None:
                mids.append(m)
            t += step_ms
        if len(mids) < 3:
            return 0.0
        rets = [math.log(mids[i + 1] / mids[i]) for i in range(len(mids) - 1)]
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var) * 1e4

    def _ret_bps(self, as_of: int, lookback_ms: int, mid: float) -> float:
        past = self._mid_at(as_of - lookback_ms)
        return 0.0 if past is None else math.log(mid / past) * 1e4

    def _context_at(self, name: str, t: int) -> float | None:
        pts = self._context.get(name)
        if not pts:
            return None
        val = None
        for p in pts:
            if p.ts_received_ms <= t:
                val = p.value
            else:
                break
        return val

    def snapshot(self, as_of_ms: int, portfolio: Portfolio) -> Snapshot:
        if as_of_ms < self._last_ingest_ms:
            # On a déjà ingéré des données postérieures à as_of : les fenêtres
            # bisect restent correctes, mais on interdit ce cas en direct pour
            # que la boucle live et le replay suivent exactement le même chemin.
            raise CausalityError("snapshot demandé dans le passé de l'ingestion")
        book = self._book_at(as_of_ms)
        if book is None:
            raise CausalityError("aucun carnet disponible à as_of")
        bid, ask = book.bids[0], book.asks[0]
        mid = (bid.price + ask.price) / 2
        spread_bps = (ask.price - bid.price) / mid * 1e4

        def imb(n: int) -> float:
            b = sum(l.size for l in book.bids[:n])
            a = sum(l.size for l in book.asks[:n])
            return 0.0 if a + b == 0 else (b - a) / (b + a)

        depth5 = sum(l.price * l.size for l in book.bids[:5]) + sum(l.price * l.size for l in book.asks[:5])

        t5 = as_of_ms - 300_000
        buy = sell = 0.0
        n5 = 0
        for tr in reversed(self._trades):
            if tr.ts_received_ms > as_of_ms:
                raise CausalityError("trade du futur dans la fenêtre")
            if tr.ts_received_ms < t5:
                break
            n5 += 1
            if tr.aggressor is Side.BUY:
                buy += tr.size
            else:
                sell += tr.size
        flow = 0.0 if buy + sell == 0 else (buy - sell) / (buy + sell)

        eq = portfolio.equity(mid)
        pos_frac = 0.0 if eq <= 0 else portfolio.position_qty * mid / eq
        upnl_bps = 0.0
        if portfolio.position_qty and portfolio.avg_entry:
            sign = 1 if portfolio.position_qty > 0 else -1
            upnl_bps = sign * (mid / portfolio.avg_entry - 1) * 1e4
        peak = max(portfolio.peak_equity, eq)
        dd = 0.0 if peak <= 0 else (1 - eq / peak) * 100
        day_pnl = 0.0 if portfolio.day_start_equity <= 0 else (eq / portfolio.day_start_equity - 1) * 100

        funding = self._context_at("funding_8h_bps", as_of_ms)
        oi_now = self._context_at("open_interest", as_of_ms)
        oi_then = self._context_at("open_interest", as_of_ms - 3_600_000)
        oi_chg = None if not oi_now or not oi_then else (oi_now / oi_then - 1) * 100

        snap = Snapshot(
            symbol=self.symbol,
            as_of_ms=as_of_ms,
            book_age_ms=as_of_ms - book.ts_received_ms,
            mid=mid,
            spread_bps=spread_bps,
            imb_l1=imb(1),
            imb_l5=imb(5),
            depth5_usd=depth5,
            rv_1m_bps=self._rv_bps(as_of_ms, 60_000),
            rv_15m_bps=self._rv_bps(as_of_ms, 900_000, step_ms=15_000),
            ret_5m_bps=self._ret_bps(as_of_ms, 300_000, mid),
            ret_1h_bps=self._ret_bps(as_of_ms, 3_600_000, mid),
            flow_imb_5m=flow,
            trades_5m=n5,
            funding_8h_bps=funding,
            oi_chg_1h_pct=oi_chg,
            pos_frac=pos_frac,
            upnl_bps=upnl_bps,
            dd_pct=dd,
            day_pnl_pct=day_pnl,
        )
        n_tok = estimate_tokens(snap.to_prompt())
        if n_tok >= MAX_SNAPSHOT_TOKENS:
            raise ValueError(f"instantané trop gros : ~{n_tok} tokens")
        return snap
