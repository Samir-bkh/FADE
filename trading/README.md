# fade-trader : agent de trading crypto autonome (cerveau / réflexe / risque)

> **Statut.** Le système tourne en papier sur un marché synthétique, et les 26 tests passent. Il n'est **pas** prêt pour le réel. Les portes 2, 4 et 5 de `docs/BUILD_PLAN.md` restent à franchir.

## Architecture

```
            flux carnet / trades / contexte (horodatage de réception)
                              │
                   ┌──────────▼───────────┐
                   │  StateEngine (code)  │  causal strict, déterministe, < 400 tokens
                   └──────────┬───────────┘
                              │ instantané texte (seule chose que Jev voit)
      kill switch ◄── RiskGate.update_breakers (code) : drawdown 15 %, perte jour
                              │
                   ┌──────────▼───────────┐
                   │  RÉFLEXE : Jev       │  1 appel, 5 questions typées en parallèle
                   └──────────┬───────────┘  échec / timeout / sortie invalide -> HOLD
                              │ JevDecision (probabilités)
                   ┌──────────▼───────────┐
                   │  Policy (code)       │  filtres, quart de Kelly, stops, sorties
                   └───┬──────────────┬───┘
     conf < 0,60       │              │
     ou crise   ┌──────▼──────┐       │
                │ CERVEAU :   │ asynchrone ; ne peut que veto / réduire / maintenir
                │ Opus 5.5    │ échec ou refus = veto (fail-safe)
                └──────┬──────┘       │
                   ┌───▼──────────────▼───┐
                   │  RiskGate.check      │  vérifié avant CHAQUE ordre
                   └──────────┬───────────┘
                   PaperBroker -> Journal JSONL -> revue de nuit
```

Jev juge, le code décide. Aucune limite, aucun seuil et aucune taille n'est lu dans une sortie de modèle.

## Démarrage

```bash
cd trading
pip install -e '.[brain,dev]'
python -m pytest -q                         # 26 tests
fade-trader compile-schemas                 # finalistes -> schemas/*.json
fade-trader demo --seconds 86400            # papier, marché synthétique, réflexe scripté
fade-trader nightly --symbol BTC-USDT --journal state/demo/journal.jsonl
fade-trader kill --engage "raison"          # ou : touch state/KILL
```

Pour utiliser le vrai Jev :

```bash
export TYPESAFE_API_KEY=...
fade-trader demo --reflex jev
```

`TYPESAFE_URL` et `JEV_MODEL` sont surchargeables. Le format filaire est **à vérifier** contre `docs.typesafe.ai` : c'est la porte 2.

La démo utilise un signal planté dans un marché synthétique. Son équité finale ne dit **rien** d'une rentabilité réelle. Elle sert à exercer la tuyauterie et à montrer que la revue de nuit détecte un réflexe mal calibré. Sur le réflexe scripté, elle mesure 93 % de confiance pour ~53 % de réussite, et le calibrateur dégonfle Kelly en conséquence.

## Schéma Jev

Les cinq questions communes sont définies dans `fade_trader/jev.py:core_questions`. Les énoncés et les thèses de chaque finaliste sont dans `schemas/<SYMBOL>.json`.

Règles d'entrée, appliquées dans `fade_trader/policy.py` (toutes obligatoires) :

- `setup_quality >= 2`
- `direction != neutral` et confiance de direction **> 0,80** (confiance brute de Jev)
- `risk_state == safe`
- `toxic_flow < 0,50`
- pas de revue Opus en cours, pas de veto actif
- espérance positive **après coûts** (frais, slippage, spread)

Dimensionnement :

- `p` est la probabilité de gain **calibrée** : courbe isotone de la revue de nuit, ou à défaut un rétrécissement de moitié vers 0,5.
- f* est le Kelly classique avec un gain `b − coût` et une perte `1 + coût`, en R.
- La fraction risquée vaut `min(0,25 × f*, 0,5 % de l'équité)`. La validation de `PolicyConfig` impose ce plafond du quart de Kelly.
- Le notionnel vaut le risque divisé par la distance du stop (coûts inclus). Il est ensuite plafonné par `RiskGate`.

## Risque (`fade_trader/risk.py`)

| Limite | Valeur | Effet |
|---|---|---|
| Drawdown max | 15 % depuis le pic | kill switch + aplatissement |
| Perte quotidienne max | 3 % | kill switch + aplatissement |
| Position max | 25 % de l'équité, levier 1× | ordre tronqué ou refusé |
| Ordre max | 10 % de l'équité | ordre tronqué |
| Fraîcheur du carnet | 2 s | entrée refusée |
| Spread max | 25 bps | entrée refusée |
| Cadence | 5 s entre ordres, 200 par jour | refus |

Invariants :

1. Les limites sont des constantes. `tighten()` ne peut que les durcir.
2. Le kill switch est vérifié avant chaque ordre. Il est persisté sur disque et seul l'opérateur le relâche.
3. Kill switch engagé : aucun appel modèle, aplatissement uniquement.
4. Un ordre reduce-only ne peut jamais agrandir ni retourner une position. Il passe même avec le kill switch ou des données périmées, car sortir du risque prime.
5. Le verdict d'Opus est borné par `escalation.enforce` : un veto gèle les entrées 15 min minimum, et aucune ouverture n'est possible.

## Revue de nuit (`fade_trader/review.py`, `scripts/nightly.sh`)

1. **Étiquetage.** Chaque décision journalisée, exécutée ou filtrée, est étiquetée par le rendement à l'horizon du schéma, coûts inclus.
2. **Mesures.**
   - Brier multi-classe de la direction, comparé à la climatologie : Brier skill score.
   - Brier binaire de la direction choisie, ECE, table de fiabilité.
   - Raisons de HOLD et gagnants manqués.
3. **Calibrateur.** Courbe isotone (PAV), seulement à partir de 200 observations. Elle ne peut que **dégonfler** la confiance.
4. **Réécriture optionnelle** (`--brain`). Opus 5.5 réécrit les énoncés en ne voyant que les 70 % les plus anciens. Les clés, options, horizon, R:R et stop sont verrouillés par le code. Les deux schémas sont évalués en ombre sur les 30 % récents. Le candidat est marqué `promotable` seulement s'il bat le courant.
5. **Promotion.** `fade-trader promote` est le seul chemin vers la production. C'est une porte opérateur : le schéma précédent est archivé.

## Choix techniques

- **Opus 5.5** (`claude-opus-5-5`) via `client.messages.parse` avec un modèle Pydantic, effort `high`.
- **Pas de modèle de repli** sur un refus : un refus vaut déjà veto, ce qui est le comportement voulu pour une revue de risque.
- **Jev.** Endpoint `api.typesafe.ai/v1/systemone`, d'après des sources tierces : OpenRouter, AIMLAPI, DataCamp, flaviocopes. La latence annoncée par le vendeur est de 70 à 500 ms. Les ~81 ms de la spécification ne sont pas vérifiées. Le timeout client est de 0,5 s, sans retry dans le chemin chaud.

---

## EN QUOI POURRAIS-JE AVOIR TORT ?

1. **L'avantage n'est pas démontré.** Rien dans ce dépôt ne prouve que Jev, sur un instantané de carnet de 7 lignes, prédit la direction à 60 minutes mieux que la climatologie. La seule mesure faite porte sur des données synthétiques. **Hypothèse nulle par défaut : il n'y a pas d'avantage.** La porte 4 existe pour la rejeter ou non.
2. **La confiance n'est pas une probabilité.** Le seuil de 0,80 porte sur la confiance brute de Jev, pas sur une fréquence de gain. Si Jev est sur-confiant sur ce domaine, ce qui est probable pour un modèle généraliste, le filtre laisse passer des paris à espérance nulle. Le calibrateur et le test de coût sont le vrai garde-fou, et le premier exige 200 observations.
3. **Coûts et slippage.** Les 12 bps aller-retour plus le spread sont une **estimation**. Sur PUMP ou ENA, le slippage réel d'un ordre au marché peut dépasser l'avantage, et le courtier papier, qui balaie le carnet visible, sous-estime l'impact. Le funding d'un short (PUMP, ETH) n'est pas encore modélisé. C'est le scénario d'échec le plus probable.
4. **Les catalyseurs sont dans le prix.** Les déblocages HYPE du 06/12 et ENA du 01-02/12 sont publics, donc probablement arbitrés. La thèse « revenus et rachats » est déjà le narratif dominant de 2026, ce qui en fait un avantage d'incitation plus qu'un avantage organique.
5. **L'accumulation de valeur reste fragile.** HYPE accumule de la valeur par les rachats, mais ces revenus sont procycliques. PUMP rachète sans accumuler, à cause d'une offre en hausse de 29,5 %. Les métriques TVL, utilisateurs et concentration des détenteurs n'ont **pas** été collectées.
6. **Des données de seconde main, contradictoires.** Je n'ai pas pu interroger les API primaires. L'open interest varie d'un facteur 7 selon le périmètre, et les dates et montants des déblocages divergent selon la source. Toute la recherche doit être réexécutée sur sources primaires avant la phase 5.
7. **Risques opérationnels.**
   - Une seule instance d'agent et un kill switch sur fichier local : un crash de la machine laisse la position ouverte sans stop. La phase 5 exige des stops natifs sur l'exchange.
   - L'horodatage de réception protège de la fuite du futur, pas d'un horloge locale qui dérive.
8. **La revue de nuit peut sur-ajuster.** Réécrire les énoncés chaque nuit sur quelques centaines d'exemples, c'est chercher dans du bruit. La séparation 70/30, le seuil de gain minimum et la promotion manuelle réduisent ce risque sans l'éliminer. Une promotion par semaine au plus est plus saine.
9. **AgenKit et la latence de 81 ms ne sont pas vérifiés.** Je n'ai pas construit sur un outil que je n'ai pas pu identifier. Le plan en six phases ne dépend d'aucun outil.
10. **Ce qui ne repose PAS sur le modèle.** Aucune limite dure n'est déléguée à un modèle : les tests le vérifient, voir `test_escalation_can_only_restrict` et `test_agent_flattens_when_killed`. Le kill switch, les stops, les tailles et les plafonds sont dans le code. Ce système préfère ne pas trader que trader sans preuve.
