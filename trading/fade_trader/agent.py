"""Boucle en direct : un `step()` par bloc / bougie.

  instantané (code) -> coupe-circuits (code) -> Jev (jugement) -> politique (code)
  -> escalade éventuelle (Opus, asynchrone, restrictive) -> porte de risque (code)
  -> courtier -> journal

Chaque étape est journalisée en JSONL append-only : c'est la matière première
de la revue de nuit.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .escalation import EnforcedVerdict, Escalator
from .execution import Broker
from .jev import DecisionError, JevDecision, JevSchema, Reflex
from .policy import Policy, PositionClock
from .risk import RiskGate
from .state_engine import CausalityError, Snapshot, StateEngine
from .types import Action, Intent, Order, Portfolio, Side


class Journal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def write(self, kind: str, **data) -> None:
        self._fh.write(json.dumps({"kind": kind, **data}, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()


def _day_key(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _dec_dict(d: JevDecision | None) -> dict | None:
    if d is None:
        return None
    x = asdict(d)
    x.pop("raw", None)
    return x


class Agent:
    def __init__(self, schema: JevSchema, engine: StateEngine, reflex: Reflex, policy: Policy,
                 gate: RiskGate, broker: Broker, portfolio: Portfolio, journal: Journal,
                 escalator: Escalator):
        self.schema, self.engine, self.reflex, self.policy = schema, engine, reflex, policy
        self.gate, self.broker, self.pf, self.journal, self.esc = gate, broker, portfolio, journal, escalator
        self.clock = PositionClock()
        self.freeze_until_ms = 0

    def _roll_day(self, now_ms: int, mark: float) -> None:
        dk = _day_key(now_ms)
        if dk != self.pf.day_key:
            self.pf.day_key = dk
            self.pf.day_start_equity = self.pf.equity(mark)

    def _apply_review(self, v: EnforcedVerdict, snap: Snapshot) -> Intent | None:
        self.freeze_until_ms = max(self.freeze_until_ms, v.freeze_until_ms)
        self.journal.write("review", t=snap.as_of_ms, symbol=snap.symbol, **asdict(v))
        if v.action == "reduce" and snap.pos_frac != 0 and v.reduce_fraction > 0:
            return Intent(Action.REDUCE, abs(snap.pos_frac) * (1 - v.reduce_fraction), 0, f"revue Opus : {v.rationale[:80]}")
        return None

    def step(self, now_ms: int) -> dict:
        try:
            snap = self.engine.snapshot(now_ms, self.pf)
        except CausalityError as e:
            self.journal.write("skip", t=now_ms, reason=str(e))
            return {"action": "skip", "reason": str(e)}

        self._roll_day(now_ms, snap.mid)
        tripped = self.gate.update_breakers(self.pf, snap.mid)

        # Kill switch engagé : on aplatit, rien d'autre (aucun appel modèle).
        if self.gate.kill.engaged():
            intent = Intent(Action.FLATTEN, 0, 0, f"kill switch : {self.gate.kill.reason()}") if snap.pos_frac else \
                Intent(Action.HOLD, 0, 0, "kill switch engagé")
            return self._execute(intent, snap, None, tripped=tripped)

        dec: JevDecision | None = None
        err = None
        try:
            dec = self.reflex.decide(self.schema, snap.to_prompt())
        except (DecisionError, KeyError, ValueError, TypeError) as e:
            err = f"décision invalide : {e}"
        except Exception as e:  # réseau, HTTP, timeout
            err = f"{type(e).__name__}: {e}"

        intent = self.policy.decide(dec, snap, self.schema, self.clock)

        review = self.esc.pop_result(snap.symbol)
        if review:
            override = self._apply_review(review, snap)
            if override:
                intent = override

        if intent.escalate:
            self.esc.submit(snap.symbol, now_ms, {
                "symbol": snap.symbol, "as_of_ms": now_ms, "reason": intent.escalate_reason,
                "thesis": self.schema.thesis, "state": snap.to_prompt(), "jev": _dec_dict(dec),
                "policy_intent": intent.reason,
            })

        is_entry = intent.action in (Action.BUY, Action.SELL)
        if is_entry and (now_ms < self.freeze_until_ms or self.esc.busy(snap.symbol)):
            intent = Intent(Action.HOLD, 0, intent.direction, "entrées gelées (revue en cours ou veto)",
                            p_win=intent.p_win, kelly_raw=intent.kelly_raw)
        return self._execute(intent, snap, dec, err=err)

    def _execute(self, intent: Intent, snap: Snapshot, dec: JevDecision | None, **extra) -> dict:
        book = self.engine._book_at(snap.as_of_ms)
        equity = self.pf.equity(snap.mid)
        order = None
        pos = self.pf.position_qty

        if intent.action in (Action.BUY, Action.SELL):
            target_qty = intent.target_frac * equity / snap.mid * intent.direction
            delta = target_qty - pos
            if abs(delta) > 0:
                side = Side.BUY if delta > 0 else Side.SELL
                order = Order(snap.symbol, side, abs(delta), False, intent.reason, uuid.uuid4().hex[:12])
        elif intent.action in (Action.REDUCE, Action.FLATTEN) and pos != 0:
            keep = 0.0 if intent.action is Action.FLATTEN else intent.target_frac * equity / snap.mid
            qty = abs(pos) - min(abs(pos), keep)
            if qty > 0:
                side = Side.SELL if pos > 0 else Side.BUY
                order = Order(snap.symbol, side, qty, True, intent.reason, uuid.uuid4().hex[:12])

        verdict = fill = None
        if order:
            verdict = self.gate.check(order, self.pf, snap.mid, snap.as_of_ms, snap.book_age_ms,
                                      snap.spread_bps, _day_key(snap.as_of_ms))
            if verdict.allowed:
                o = Order(order.symbol, order.side, verdict.qty, order.reduce_only, order.reason, order.client_id)
                fill = self.broker.submit(o, book.asks if o.side is Side.BUY else book.bids, snap.as_of_ms, self.pf)
                if fill:
                    self.gate.record_order(snap.as_of_ms)
                    if self.pf.position_qty == 0:
                        self.clock.entry_ms = None
                    elif not o.reduce_only:
                        self.clock.entry_ms = snap.as_of_ms

        rec = {
            "t": snap.as_of_ms, "symbol": snap.symbol, "schema": self.schema.version,
            "digest": snap.digest(), "mid": snap.mid, "spread_bps": snap.spread_bps,
            "state": snap.to_prompt(), "jev": _dec_dict(dec),
            "intent": {**asdict(intent), "action": intent.action.value},
            "order": None if order is None else {**asdict(order), "side": order.side.value},
            "risk": None if verdict is None else asdict(verdict),
            "fill": None if fill is None else {"price": fill.price, "qty": fill.qty, "fee": fill.fee},
            "equity": self.pf.equity(snap.mid), "position_qty": self.pf.position_qty,
            "wall_ms": int(time.time() * 1000), **extra,
        }
        self.journal.write("step", **rec)
        return rec
