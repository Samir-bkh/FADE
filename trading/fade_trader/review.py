"""Revue de nuit.

1. Relit le journal de la session (chaque décision, exécutée ou filtrée).
2. Étiquette chaque décision a posteriori : rendement au bout de l'horizon du
   schéma, coûts inclus. (L'étiquetage regarde le futur par construction ; il
   n'alimente QUE la revue, jamais la boucle en direct.)
3. Mesure la calibration : Brier multi-classe de la direction, Brier binaire
   de la direction choisie, table de fiabilité, comparaison à la climatologie.
4. Ajuste un calibrateur isotone (PAV) -> probabilités utilisées par Kelly.
5. Propose un schéma candidat (réécriture des énoncés par Opus 5.5, en option),
   l'évalue en ombre sur les mêmes états, et ne le marque « promouvable » que
   s'il bat le schéma courant. La promotion reste un geste opérateur.
"""
from __future__ import annotations

import json
import math
from bisect import bisect_left
from collections import Counter
from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel

from .jev import JevSchema, Question, Reflex
from .policy import Calibrator

DIRS = ("long", "short", "neutral")


def load_steps(journal: Path) -> list[dict]:
    out = []
    with Path(journal).open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("kind") == "step":
                out.append(r)
    return out


def label(steps: list[dict], horizon_ms: int, cost_bps: float) -> list[dict]:
    """Ajoute 'ret_h_bps' et 'y_dir' (long/short/neutral) à chaque pas qui a
    un point futur à l'horizon. Les pas trop récents sont exclus (pas d'étiquette)."""
    ts = [s["t"] for s in steps]
    labeled = []
    for s in steps:
        j = bisect_left(ts, s["t"] + horizon_ms)
        if j >= len(steps):
            break
        r = math.log(steps[j]["mid"] / s["mid"]) * 1e4
        y = "long" if r > cost_bps else "short" if r < -cost_bps else "neutral"
        labeled.append({**s, "ret_h_bps": r, "y_dir": y})
    return labeled


def brier_multiclass(probs: list[dict], ys: list[str]) -> float:
    return sum(sum((p.get(k, 0.0) - (1.0 if y == k else 0.0)) ** 2 for k in DIRS)
               for p, y in zip(probs, ys)) / max(len(ys), 1)


def pav(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    """Régression isotone (pool-adjacent-violators). Retourne bornes sup et valeurs."""
    pts = sorted(zip(xs, ys))
    blocks = [[x, x, y, 1] for x, y in pts]  # lo, hi, somme, n
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][2] / blocks[i][3] > blocks[i + 1][2] / blocks[i + 1][3]:
            a, b = blocks[i], blocks.pop(i + 1)
            blocks[i] = [a[0], b[1], a[2] + b[2], a[3] + b[3]]
            i = max(i - 1, 0)
        else:
            i += 1
    return [b[1] for b in blocks], [b[2] / b[3] for b in blocks]


def evaluate(labeled: list[dict]) -> dict:
    rows = [r for r in labeled if r.get("jev")]
    if not rows:
        return {"n": 0}
    probs = [r["jev"]["direction"]["probs"] for r in rows]
    ys = [r["y_dir"] for r in rows]
    base = Counter(ys)
    clim = {k: base[k] / len(ys) for k in DIRS}
    bs = brier_multiclass(probs, ys)
    bs_clim = brier_multiclass([clim] * len(ys), ys)

    # Binaire : la direction choisie (hors neutre) a-t-elle gagné après coûts ?
    conf, win = [], []
    for r in rows:
        d = r["jev"]["direction"]
        if d["label"] == "neutral":
            continue
        conf.append(d["confidence"])
        win.append(1.0 if r["y_dir"] == d["label"] else 0.0)
    bs_bin = sum((c - w) ** 2 for c, w in zip(conf, win)) / max(len(conf), 1)

    bins = [0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
    table = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        sel = [w for c, w in zip(conf, win) if lo <= c < hi]
        sc = [c for c in conf if lo <= c < hi]
        if sel:
            table.append({"bin": f"[{lo:.1f},{min(hi, 1.0):.1f})", "n": len(sel),
                          "mean_conf": sum(sc) / len(sc), "hit_rate": sum(sel) / len(sel)})
    ece = sum(abs(t["mean_conf"] - t["hit_rate"]) * t["n"] for t in table) / max(len(conf), 1)

    gated = Counter(r["intent"]["reason"].split(" ")[0] for r in rows
                    if r["intent"]["action"] == "hold")
    trades = [r for r in rows if r.get("fill")]
    missed = [r for r in rows if r["intent"]["action"] == "hold" and r["jev"]["direction"]["label"] != "neutral"
              and r["y_dir"] == r["jev"]["direction"]["label"]]
    return {
        "n": len(rows), "n_directional": len(conf),
        "brier_direction_multiclass": bs, "brier_climatology": bs_clim,
        "brier_skill_score": 1 - bs / bs_clim if bs_clim > 0 else None,
        "brier_direction_binary": bs_bin, "ece": ece, "reliability": table,
        "label_base_rates": clim, "hold_reasons": dict(gated.most_common(10)),
        "n_fills": len(trades), "n_missed_winners": len(missed),
        "_conf": conf, "_win": win,
    }


def fit_calibrator(conf: list[float], win: list[float], min_obs: int = 200) -> Calibrator | None:
    """Pas de courbe sous 200 observations : on garde le rétrécissement prudent."""
    if len(conf) < min_obs:
        return None
    edges, values = pav(conf, win)
    # Jamais au-dessus de la confiance brute : on n'autorise la calibration qu'à DÉGONFLER.
    values = [min(v, e) for v, e in zip(values, edges)]
    return Calibrator(edges=edges, values=values, shrink=0.5, n_obs=len(conf))


# ------------------------------------------------------------ réécriture
class QuestionRewrite(BaseModel):
    key: str
    prompt: str


class SchemaRewrite(BaseModel):
    thesis: str
    questions: list[QuestionRewrite]
    changelog: str


def propose_rewrite(schema: JevSchema, metrics: dict) -> JevSchema:
    """Demande à Opus 5.5 de réécrire les énoncés. Seuls les textes changent :
    clés, types, options, horizon, R:R et stop sont imposés par le code."""
    import anthropic

    client = anthropic.Anthropic(timeout=600, max_retries=2)
    public = {k: v for k, v in metrics.items() if not k.startswith("_")}
    msg = (
        "Voici le schéma de décision Jev courant et ses métriques de calibration de la session. "
        "Réécris uniquement les énoncés (thesis, prompts) pour améliorer la calibration et la "
        "discrimination. N'invente aucun fait de marché. Garde chaque énoncé court.\n\n"
        f"SCHEMA:\n{json.dumps({'thesis': schema.thesis, 'questions': [q.__dict__ for q in schema.questions]}, ensure_ascii=False, default=list)}\n\n"
        f"METRIQUES:\n{json.dumps(public, ensure_ascii=False)}"
    )
    with client.messages.stream(
        model="claude-opus-5-5", max_tokens=16000, output_config={"effort": "high"},
        messages=[{"role": "user", "content": msg}], output_format=SchemaRewrite,
    ) as stream:
        final = stream.get_final_message()
    rw = final.parsed_output
    if rw is None:
        raise RuntimeError(f"réécriture inutilisable : {final.stop_reason}")
    by_key = {q.key: q.prompt for q in rw.questions}
    qs = tuple(Question(q.key, q.kind, by_key.get(q.key, q.prompt)[:600], q.options, q.levels)
               for q in schema.questions)
    return replace(schema, version=bump(schema.version), thesis=rw.thesis[:800], questions=qs)


def bump(v: str) -> str:
    head, _, n = v.rpartition(".")
    return f"{head}.{int(n) + 1}" if n.isdigit() else f"{v}.1"


def shadow_eval(reflex: Reflex, schema: JevSchema, labeled: list[dict], limit: int = 500) -> float:
    """Rejoue les états journalisés avec un schéma candidat : Brier multi-classe."""
    rows = [r for r in labeled if r.get("state")][-limit:]
    probs, ys = [], []
    for r in rows:
        try:
            d = reflex.decide(schema, r["state"])
        except Exception:
            continue
        probs.append(d.direction.probs)
        ys.append(r["y_dir"])
    return brier_multiclass(probs, ys) if ys else float("inf")


def nightly(journal: Path, schema_path: Path, out_dir: Path, cost_bps: float,
            reflex: Reflex | None = None, use_brain: bool = False, min_gain: float = 0.005) -> dict:
    schema = JevSchema.load(schema_path)
    steps = [s for s in load_steps(journal) if s.get("schema") == schema.version]
    labeled = label(steps, schema.horizon_min * 60_000, cost_bps)
    m = evaluate(labeled)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"schema": schema.version, **{k: v for k, v in m.items() if not k.startswith("_")}}

    cal = fit_calibrator(m.get("_conf", []), m.get("_win", []))
    if cal:
        (out_dir / "calibrator.candidate.json").write_text(json.dumps(cal.to_dict(), indent=2))
        report["calibrator"] = "candidat écrit (n=%d)" % cal.n_obs
    else:
        report["calibrator"] = "données insuffisantes : rétrécissement prudent conservé"

    if use_brain and reflex is not None and m.get("n", 0) >= 50:
        # Hors échantillon : la réécriture voit les 70 % les plus anciens, le
        # jugement se fait sur les 30 % les plus récents, jamais vus par Opus.
        cut = int(len(labeled) * 0.7)
        cand = propose_rewrite(schema, evaluate(labeled[:cut]))
        cur = shadow_eval(reflex, schema, labeled[cut:])
        new = shadow_eval(reflex, cand, labeled[cut:])
        report["shadow"] = {"current_brier": cur, "candidate_brier": new}
        cand_path = out_dir / f"schema.{cand.version}.json"
        cand.dump(cand_path)
        report["candidate_schema"] = str(cand_path)
        report["promotable"] = new < cur - min_gain
    else:
        report["promotable"] = False

    (out_dir / f"report.{schema.version}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return report
