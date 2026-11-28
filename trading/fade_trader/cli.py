"""Interface opérateur.

  fade-trader compile-schemas            # finalistes -> schemas/*.json
  fade-trader demo --seconds 7200        # papier sur marché synthétique (tuyauterie)
  fade-trader nightly --symbol BTC-USDT [--brain]
  fade-trader promote --symbol BTC-USDT --candidate PATH   # porte opérateur
  fade-trader kill --engage "raison" | --release | --status
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .agent import Agent, Journal
from .escalation import Escalator
from .execution import PaperBroker, assert_live_allowed
from .finalists import compile_all
from .jev import JevClient, JevSchema, ScriptedReflex
from .policy import Calibrator, Policy, PolicyConfig
from .review import nightly
from .risk import HARD_LIMITS, KillSwitch, RiskGate
from .sim import synthetic_stream
from .state_engine import StateEngine
from .types import ContextPoint, OrderBook, Portfolio, Trade

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS, STATE = ROOT / "schemas", ROOT / "state"


def _reflex(kind: str):
    if kind == "scripted":
        return ScriptedReflex()
    return JevClient(os.environ.get("TYPESAFE_API_KEY", ""),
                     base_url=os.environ.get("TYPESAFE_URL", "https://api.typesafe.ai/v1/systemone"),
                     model=os.environ.get("JEV_MODEL", "jev-latest"))


def cmd_demo(a) -> None:
    sym = a.symbol
    schema = JevSchema.load(SCHEMAS / f"{sym}.json")
    state = STATE / "demo"
    if state.exists():
        shutil.rmtree(state)
    kill = KillSwitch(state / "KILL")
    eng = StateEngine(sym)
    pf = Portfolio(cash=a.equity, peak_equity=a.equity)
    agent = Agent(schema, eng, _reflex(a.reflex), Policy(PolicyConfig(), Calibrator.load(STATE / f"{sym}.calibrator.json")),
                  RiskGate(HARD_LIMITS, kill), PaperBroker(), pf, Journal(state / "journal.jsonl"),
                  Escalator(enabled=False))
    start = 1_764_288_000_000
    fills = holds = 0
    for t, events in synthetic_stream(sym, start, a.seconds, seed=a.seed):
        for e in events:
            if isinstance(e, OrderBook):
                eng.on_book(e)
            elif isinstance(e, Trade):
                eng.on_trade(e)
        if (t - start) % (a.block_s * 1000) == 0 and t - start >= 300_000:
            r = agent.step(t)
            fills += bool(r.get("fill"))
            holds += r.get("intent", {}).get("action") == "hold"
    last = eng.snapshot(t, pf)
    print(json.dumps({
        "avertissement": "marché synthétique + réflexe scripté : test de tuyauterie, pas une performance",
        "equity_finale": round(pf.equity(last.mid), 2), "frais": round(pf.fees_paid, 2),
        "fills": fills, "holds": holds, "kill_switch": kill.engaged(),
        "journal": str(state / "journal.jsonl"),
    }, indent=2, ensure_ascii=False))


def cmd_nightly(a) -> None:
    rep = nightly(Path(a.journal), SCHEMAS / f"{a.symbol}.json", STATE / "review" / a.symbol,
                  cost_bps=PolicyConfig().roundtrip_cost_bps,
                  reflex=_reflex(a.reflex) if a.brain else None, use_brain=a.brain)
    print(json.dumps(rep, indent=2, ensure_ascii=False))


def cmd_promote(a) -> None:
    cand = JevSchema.load(Path(a.candidate))
    rep_dir = Path(a.candidate).parent
    reports = sorted(rep_dir.glob("report.*.json"))
    if not reports or not json.loads(reports[-1].read_text()).get("promotable"):
        sys.exit("Refusé : le dernier rapport ne marque pas ce candidat comme promouvable.")
    dst = SCHEMAS / f"{a.symbol}.json"
    archive = SCHEMAS / "archive"
    archive.mkdir(exist_ok=True)
    old = JevSchema.load(dst)
    shutil.copy(dst, archive / f"{old.version}.json")
    cand.dump(dst)
    cal = rep_dir / "calibrator.candidate.json"
    if cal.exists():
        shutil.copy(cal, STATE / f"{a.symbol}.calibrator.json")
    print(f"Promu : {old.version} -> {cand.version}")


def cmd_kill(a) -> None:
    k = KillSwitch(STATE / "KILL")
    if a.engage:
        k.engage(a.engage)
    elif a.release:
        k.release()
    print(json.dumps({"engaged": k.engaged(), "reason": k.reason() if k.engaged() else None}))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="fade-trader")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("compile-schemas")
    d = sub.add_parser("demo")
    d.add_argument("--symbol", default="BTC-USDT")
    d.add_argument("--seconds", type=int, default=7200)
    d.add_argument("--block-s", type=int, default=60)
    d.add_argument("--equity", type=float, default=10_000)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--reflex", choices=["scripted", "jev"], default="scripted")
    n = sub.add_parser("nightly")
    n.add_argument("--symbol", required=True)
    n.add_argument("--journal", required=True)
    n.add_argument("--brain", action="store_true", help="réécriture du schéma par Opus 5.5 + évaluation en ombre")
    n.add_argument("--reflex", choices=["scripted", "jev"], default="jev")
    pr = sub.add_parser("promote")
    pr.add_argument("--symbol", required=True)
    pr.add_argument("--candidate", required=True)
    k = sub.add_parser("kill")
    g = k.add_mutually_exclusive_group()
    g.add_argument("--engage", metavar="RAISON")
    g.add_argument("--release", action="store_true")
    g.add_argument("--status", action="store_true")
    r = sub.add_parser("live")
    r.add_argument("--symbol", required=True)
    a = p.parse_args(argv)

    if a.cmd == "compile-schemas":
        for path in compile_all(SCHEMAS):
            print(path)
    elif a.cmd == "demo":
        cmd_demo(a)
    elif a.cmd == "nightly":
        cmd_nightly(a)
    elif a.cmd == "promote":
        cmd_promote(a)
    elif a.cmd == "kill":
        cmd_kill(a)
    elif a.cmd == "live":
        assert_live_allowed()


if __name__ == "__main__":
    main()
