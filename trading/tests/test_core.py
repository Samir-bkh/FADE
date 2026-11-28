import json
import math

import pytest

from fade_trader.agent import Agent, Journal
from fade_trader.escalation import Escalator, ReviewVerdict, enforce
from fade_trader.execution import PaperBroker, apply_fill
from fade_trader.jev import (Choice, DecisionError, JevDecision, JevSchema, ScriptedReflex, TypeSafeWire,
                             core_questions, validate)
from fade_trader.policy import Calibrator, Policy, PolicyConfig, PositionClock, kelly_risk_fraction
from fade_trader.review import brier_multiclass, evaluate, label, pav
from fade_trader.risk import HARD_LIMITS, KillSwitch, RiskGate, RiskLimits, tighten
from fade_trader.state_engine import MAX_SNAPSHOT_TOKENS, CausalityError, StateEngine, estimate_tokens
from fade_trader.types import Action, BookLevel, OrderBook, Order, Portfolio, Side, Trade

T0 = 1_764_288_000_000


def book(t, px=100.0, sym="X"):
    return OrderBook(sym, t, t, tuple(BookLevel(px - 0.01 - i * 0.01, 10) for i in range(5)),
                     tuple(BookLevel(px + 0.01 + i * 0.01, 10) for i in range(5)))


def schema():
    return JevSchema("X.v1.0", "X", "test", horizon_min=60, reward_risk=2.0, stop_bps=100,
                     questions=core_questions(""))


def decision(direction="long", conf=0.9, q=3, regime="trending", risk="safe", toxic=0.1):
    other = (1 - conf) / 2
    probs = {d: (conf if d == direction else other) for d in ("long", "short", "neutral")}
    rp = {r: (0.97 if r == regime else 0.01) for r in ("trending", "mean_reverting", "high_vol", "crisis")}
    sp = {r: (0.98 if r == risk else 0.01) for r in ("safe", "near_limit", "reduce")}
    return JevDecision(Choice(regime, rp, 0.97), Choice(direction, probs, conf), toxic, q, {}, Choice(risk, sp, 0.98), 1.0)


# ------------------------------------------------------------ moteur d'état
def test_snapshot_is_causal_and_small():
    e = StateEngine("X")
    for i in range(400):
        e.on_book(book(T0 + i * 1000, 100 + math.sin(i / 10)))
        e.on_trade(Trade("X", T0 + i * 1000, 100, 1, Side.BUY))
    pf = Portfolio(cash=1000, peak_equity=1000)
    s = e.snapshot(T0 + 399_000, pf)
    assert estimate_tokens(s.to_prompt()) < MAX_SNAPSHOT_TOKENS
    assert s.book_age_ms == 0 and s.trades_5m == 301
    # déterminisme
    assert s.digest() == e.snapshot(T0 + 399_000, pf).digest()
    with pytest.raises(CausalityError):
        e.snapshot(T0 + 100_000, pf)       # demande dans le passé de l'ingestion
    with pytest.raises(CausalityError):
        e.on_book(book(T0 + 1000))         # événement hors d'ordre


def test_snapshot_ignores_future_book():
    e = StateEngine("X")
    e.on_book(book(T0, 100))
    s = e.snapshot(T0 + 1500, Portfolio(cash=1000))
    assert s.mid == pytest.approx(100) and s.book_age_ms == 1500


# ------------------------------------------------------------ risque
def test_tighten_never_loosens():
    L = tighten(HARD_LIMITS, {"max_drawdown_pct": 50, "max_daily_loss_pct": 1, "min_order_interval_ms": 1})
    assert L.max_drawdown_pct == 15.0 and L.max_daily_loss_pct == 1.0 and L.min_order_interval_ms == 5000


def test_drawdown_trips_kill_switch_and_only_reductions_pass(tmp_path):
    k = KillSwitch(tmp_path / "KILL")
    g = RiskGate(HARD_LIMITS, k)
    pf = Portfolio(cash=0, position_qty=10, avg_entry=100, peak_equity=1000, day_start_equity=1000)
    assert g.update_breakers(pf, 84.0) in ("drawdown", "daily_loss")
    assert k.engaged()
    buy = Order("X", Side.BUY, 1, False, "t", "a")
    assert not g.check(buy, pf, 84, T0, 0, 1, "d").allowed
    sell = Order("X", Side.SELL, 50, True, "flatten", "b")
    v = g.check(sell, pf, 84, T0, 10_000, 999, "d")       # même données périmées : la sortie passe
    assert v.allowed and v.qty == 10


def test_reduce_only_cannot_increase(tmp_path):
    g = RiskGate(HARD_LIMITS, KillSwitch(tmp_path / "K"))
    pf = Portfolio(cash=1000, position_qty=1, avg_entry=100, peak_equity=1100, day_start_equity=1100)
    assert not g.check(Order("X", Side.BUY, 1, True, "", "a"), pf, 100, T0, 0, 1, "d").allowed


def test_position_and_order_caps(tmp_path):
    g = RiskGate(HARD_LIMITS, KillSwitch(tmp_path / "K"))
    pf = Portfolio(cash=10_000, peak_equity=10_000, day_start_equity=10_000)
    v = g.check(Order("X", Side.BUY, 1_000, False, "", "a"), pf, 100, T0, 0, 1, "d")
    assert v.allowed and v.qty == pytest.approx(10)            # 10 % de l'équité par ordre
    pf.position_qty, pf.cash = 25, 7_500                        # déjà à 25 %
    v = g.check(Order("X", Side.BUY, 5, False, "", "b"), pf, 100, T0 + 10_000, 0, 1, "d")
    assert not v.allowed


def test_stale_and_wide_spread_block_entries(tmp_path):
    g = RiskGate(HARD_LIMITS, KillSwitch(tmp_path / "K"))
    pf = Portfolio(cash=10_000, peak_equity=10_000, day_start_equity=10_000)
    o = Order("X", Side.BUY, 1, False, "", "a")
    assert not g.check(o, pf, 100, T0, 5_000, 1, "d").allowed
    assert not g.check(o, pf, 100, T0, 0, 100, "d").allowed


# ------------------------------------------------------------ politique
def snap_for(e_price=100.0, pos=0.0):
    e = StateEngine("X")
    e.on_book(book(T0, e_price))
    pf = Portfolio(cash=10_000 - pos * e_price, position_qty=pos, avg_entry=e_price if pos else 0,
                   peak_equity=10_000, day_start_equity=10_000)
    return e.snapshot(T0, pf)


@pytest.mark.parametrize("kw,reason", [
    (dict(q=1), "setup_quality"), (dict(conf=0.80), "confiance"), (dict(risk="near_limit"), "risk_state"),
    (dict(toxic=0.7), "toxique"), (dict(direction="neutral"), "neutre"),
])
def test_entry_gates(kw, reason):
    pol = Policy(PolicyConfig(), Calibrator(shrink=1.0))
    it = pol.decide(decision(**kw), snap_for(), schema(), PositionClock())
    assert it.action is Action.HOLD and reason in it.reason


def test_entry_sizing_quarter_kelly_and_risk_cap():
    pol = Policy(PolicyConfig(), Calibrator(shrink=1.0))
    it = pol.decide(decision(conf=0.9), snap_for(), schema(), PositionClock())
    assert it.action is Action.BUY
    risk = it.target_frac * (100 + 12 + snap_for().spread_bps) / 1e4
    assert risk <= 0.005 + 1e-12
    assert risk <= 0.25 * it.kelly_raw + 1e-12


def test_low_conf_and_crisis_escalate():
    pol = Policy(PolicyConfig(), Calibrator())
    assert pol.decide(decision(conf=0.55), snap_for(), schema(), PositionClock()).escalate
    it = pol.decide(decision(regime="crisis"), snap_for(pos=10), schema(), PositionClock())
    assert it.escalate and it.action is Action.REDUCE


def test_no_decision_holds():
    pol = Policy(PolicyConfig(), Calibrator())
    assert pol.decide(None, snap_for(), schema(), PositionClock()).action is Action.HOLD


def test_kelly_formula_and_costs():
    assert kelly_risk_fraction(0.5, 1.0, 0.0) == 0.0
    assert kelly_risk_fraction(0.6, 1.0, 0.0) == pytest.approx(0.2)
    assert kelly_risk_fraction(0.6, 1.0, 0.3) < 0.2
    with pytest.raises(ValueError):
        PolicyConfig(kelly_mult=0.5)
    with pytest.raises(ValueError):
        PolicyConfig(min_direction_conf=0.7)


def test_default_calibrator_shrinks():
    assert Calibrator()(0.9) == pytest.approx(0.7)


# ------------------------------------------------------------ Jev
def test_validate_rejects_bad_distribution():
    d = decision()
    bad = JevDecision(d.regime, Choice("long", {"long": 0.9, "short": 0.9, "neutral": 0}, 0.9), 0.1, 3, {}, d.risk_state, 1)
    with pytest.raises(DecisionError):
        validate(bad, schema())


def test_wire_roundtrip():
    payload = TypeSafeWire.build(schema(), "mid=1", "jev-latest")
    assert {q["name"] for q in payload["questions"]} == {"regime", "direction", "toxic_flow", "setup_quality", "risk_state"}
    body = {"answers": [
        {"name": "regime", "answer": "trending", "probabilities": {"trending": .7, "mean_reverting": .1, "high_vol": .1, "crisis": .1}, "confidence": .7},
        {"name": "direction", "answer": "long", "probabilities": {"long": .85, "short": .1, "neutral": .05}, "confidence": .85},
        {"name": "toxic_flow", "probability": 0.2},
        {"name": "setup_quality", "score": 2, "probabilities": {"0": .1, "1": .2, "2": .5, "3": .2}},
        {"name": "risk_state", "answer": "safe", "probabilities": {"safe": .9, "near_limit": .05, "reduce": .05}, "confidence": .9},
    ]}
    d = validate(TypeSafeWire.parse(body, 81.0), schema())
    assert d.direction.label == "long" and d.setup_quality == 2 and d.latency_ms == 81.0


# ------------------------------------------------------------ escalade
def test_escalation_can_only_restrict():
    v = enforce(ReviewVerdict(action="veto", reduce_fraction=0.9, freeze_minutes=0, rationale="x"), T0)
    assert v.reduce_fraction == 0 and v.freeze_until_ms >= T0 + 15 * 60_000
    v = enforce(ReviewVerdict(action="reduce", reduce_fraction=0.5, freeze_minutes=5, rationale="x"), T0)
    assert v.reduce_fraction == 0.5


def test_disabled_brain_fails_safe():
    esc = Escalator(enabled=False, cooldown_s=0)
    assert esc.submit("X", T0, {})
    assert esc.pop_result("X").action == "veto"


# ------------------------------------------------------------ exécution
def test_apply_fill_pnl():
    pf = Portfolio(cash=1000)
    apply_fill(pf, Side.BUY, 1, 100, 0)
    apply_fill(pf, Side.SELL, 1, 110, 0)
    assert pf.position_qty == 0 and pf.realized_pnl == pytest.approx(10) and pf.cash == pytest.approx(1010)


# ------------------------------------------------------------ boucle
def test_agent_flattens_when_killed(tmp_path):
    e = StateEngine("X")
    k = KillSwitch(tmp_path / "KILL")
    pf = Portfolio(cash=9_000, position_qty=10, avg_entry=100, peak_equity=10_000, day_start_equity=10_000)
    ag = Agent(schema(), e, ScriptedReflex(), Policy(PolicyConfig(), Calibrator()), RiskGate(HARD_LIMITS, k),
               PaperBroker(), pf, Journal(tmp_path / "j.jsonl"), Escalator(enabled=False))
    e.on_book(book(T0, 100))
    k.engage("test")
    r = ag.step(T0)
    assert r["fill"] and pf.position_qty == 0
    assert r["jev"] is None                          # aucun appel modèle kill switch engagé


def test_agent_reflex_failure_holds(tmp_path):
    class Boom:
        def decide(self, *a):
            raise TimeoutError("lent")
    e = StateEngine("X")
    ag = Agent(schema(), e, Boom(), Policy(PolicyConfig(), Calibrator()), RiskGate(HARD_LIMITS, KillSwitch(tmp_path / "K")),
               PaperBroker(), Portfolio(cash=10_000, peak_equity=10_000), Journal(tmp_path / "j.jsonl"), Escalator(enabled=False))
    e.on_book(book(T0))
    r = ag.step(T0)
    assert r["intent"]["action"] == "hold" and "TimeoutError" in r["err"]


# ------------------------------------------------------------ revue
def test_pav_monotone():
    edges, vals = pav([0.6, 0.7, 0.8, 0.9], [1, 0, 1, 0])
    assert all(a <= b for a, b in zip(vals, vals[1:]))


def test_brier_and_labels():
    assert brier_multiclass([{"long": 1, "short": 0, "neutral": 0}], ["long"]) == 0
    steps = [{"t": T0 + i * 60_000, "mid": 100 * (1.01 if i % 2 else 1), "jev": None,
              "intent": {"action": "hold", "reason": "x"}} for i in range(10)]
    lab = label(steps, 60_000, 12)
    assert lab[0]["y_dir"] == "long" and lab[1]["y_dir"] == "short"
    assert evaluate(lab)["n"] == 0
