"""Marché synthétique pour tests et démonstration de la tuyauterie.

Marche aléatoire avec régimes de volatilité. AUCUN résultat obtenu ici ne dit
quoi que ce soit de la rentabilité d'une stratégie réelle.
"""
from __future__ import annotations

import math
import random
from collections.abc import Iterator

from .types import BookLevel, OrderBook, Side, Trade


def synthetic_stream(symbol: str, start_ms: int, n_seconds: int, seed: int = 7,
                     px0: float = 60_000.0, tick: float = 0.5) -> Iterator[tuple[int, list]]:
    rng = random.Random(seed)
    px = px0
    vol = 2e-4
    bias = 0.0   # état caché : persistance du flux qui précède le prix (signal planté pour exercer la tuyauterie)
    for i in range(n_seconds):
        t = start_ms + i * 1000
        if rng.random() < 0.002:
            vol = rng.choice([1e-4, 2e-4, 6e-4])
        if rng.random() < 0.003:
            bias = rng.choice([-0.35, 0.0, 0.0, 0.35])
        drift = bias * vol * 0.25
        px *= math.exp(drift + vol * rng.gauss(0, 1))
        half = max(tick, px * 1e-5)
        bids = tuple(BookLevel(round(px - half - k * tick, 2), round(rng.uniform(0.2, 2.0), 4)) for k in range(10))
        asks = tuple(BookLevel(round(px + half + k * tick, 2), round(rng.uniform(0.2, 2.0), 4)) for k in range(10))
        events: list = []
        for _ in range(rng.randint(0, 4)):
            side = Side.BUY if rng.random() < 0.5 + bias else Side.SELL
            events.append(Trade(symbol, t, asks[0].price if side is Side.BUY else bids[0].price,
                                round(rng.uniform(0.01, 0.5), 4), side))
        events.append(OrderBook(symbol, t - 5, t, bids, asks))
        yield t, events
