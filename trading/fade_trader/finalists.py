"""Compilation des finalistes de la recherche en schémas Jev v1.

Les thèses sont des RÉSUMÉS de docs/RESEARCH.md ; elles ne contiennent que des
faits sourcés (datés) ou des énoncés explicitement marqués comme hypothèses.
Les paramètres horizon / R:R / stop sont des choix de conception du code
(ESTIMATIONS initiales, à recalibrer en papier), pas des mesures.
"""
from __future__ import annotations

from pathlib import Path

from .jev import JevSchema, core_questions

FINALISTS = [
    dict(
        symbol="BTC-USDT",
        thesis=("Régime 2026-11 : BTC ~60-64k, Fear&Greed 11 (19/11), sorties ETF spot ~2,7 Md$ sur 30 j, "
                "funding proche de neutre. Hypothèse : capitulation -> rebonds de retour à la moyenne "
                "tradables, tendance de fond baissière. Pas de long sans absorption visible du flux vendeur."),
        hint="Biais : neutre à long uniquement sur absorption ; short autorisé si cassure avec flux vendeur.",
        horizon_min=60, reward_risk=1.8, stop_bps=80,
    ),
    dict(
        symbol="ETH-USDT",
        thesis=("ETH ~1 670-1 740 $ (27/11), sous résistance ~1 982 $ (Au79), dominance ETH ~10 %, "
                "dominance BTC ~58-60 %. Hypothèse : faiblesse relative persistante vs BTC."),
        hint="Biais : short ou neutre tant que la faiblesse relative persiste ; long seulement contre-tendance court.",
        horizon_min=60, reward_risk=1.8, stop_bps=100,
    ),
    dict(
        symbol="HYPE-USDT",
        thesis=("Hyperliquid : ~80 M$ de revenus protocole sur 30 j (DefiLlama, ~27/11), quasi-totalité vers "
                "rachats HYPE ; rachats 2026 ~791 M$ pour +0,43 % d'offre circulante (12/11). Catalyseur "
                "négatif confirmé : déblocage contributeurs jusqu'à 9,92 M HYPE le 06/12."),
        hint="Biais : long sur repli si flux acheteur ; neutre/short autour du déblocage du 06/12.",
        horizon_min=120, reward_risk=2.0, stop_bps=150,
    ),
    dict(
        symbol="PUMP-USDT",
        thesis=("Pump : rachats ~407 M$ en 2026 mais offre circulante +29,5 % (12/11) : la valeur est diluée. "
                "Déblocage annoncé ~14/12 (source unique, à confirmer)."),
        hint="Biais : short sur rebonds faibles ; aucun long de conviction.",
        horizon_min=60, reward_risk=1.6, stop_bps=200,
    ),
    dict(
        symbol="ENA-USDT",
        thesis=("Ethena : déblocage début décembre, montant et date divergents selon les sources "
                "(~28 M$ le 01/12 vs ~94 M$ le 02/12). Trade d'événement, pas de thèse fondamentale."),
        hint="Biais : neutre ; trader uniquement la réaction au déblocage, dans le sens du flux.",
        horizon_min=30, reward_risk=1.5, stop_bps=150,
    ),
]


def compile_all(out_dir: Path, version: str = "v1.0") -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for f in FINALISTS:
        s = JevSchema(version=f"{f['symbol']}.{version}", symbol=f["symbol"], thesis=f["thesis"],
                      horizon_min=f["horizon_min"], reward_risk=f["reward_risk"], stop_bps=f["stop_bps"],
                      questions=core_questions(f["hint"]))
        p = out_dir / f"{f['symbol']}.json"
        s.dump(p)
        paths.append(p)
    return paths
