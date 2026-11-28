# Recherche de marché — 28 novembre 2026

**Étiquettes utilisées.** Chaque affirmation porte l'une de ces étiquettes :

- **[SOURCE, date]** : chiffre repris d'une source datée, citée en bas de page.
- **[ESTIMATION]** : calcul ou paramètre de conception de ma part.
- **[SPÉCULATION]** : hypothèse non démontrée.
- **[NON VÉRIFIÉ]** : métrique demandée que je n'ai pas pu collecter. Elle est laissée vide plutôt qu'inventée.

**Limite de méthode.** Le conteneur de construction n'avait pas d'accès réseau direct aux API de marché (Binance, CoinGecko, DefiLlama ont toutes été bloquées). Les chiffres ci-dessous viennent donc de recherches web portant sur des articles et des tableaux de bord datés, pas de requêtes brutes sur les API. Les sources se contredisent souvent ; quand c'est le cas, j'affiche la fourchette. **Avant la phase 5 (papier en direct), toute la recherche doit être réexécutée par le module de collecte sur les API primaires.**

---

## 1. Régime de marché

| Indicateur | Lecture | Étiquette |
|---|---|---|
| Prix BTC | ~60–64 k$ fin novembre ; marque 60 464 $ le 26/11 ; pic intrajournalier à 64 451 $ le 23/11 | [SOURCE TokenPost 26/11, AlertaChart 23/11] |
| Sentiment | Fear & Greed 11 (« peur extrême ») le 19/11 | [SOURCE CoinStats] |
| Flux ETF spot BTC | −2,72 Md$ sur 30 j, −1,04 Md$ sur 7 j | [SOURCE CoinStats] |
| Funding BTC | +0,0004 % à +0,0100 % par 8 h selon la source et le jour : neutre à légèrement positif | [SOURCE AlertaChart 23/11, TokenPost 26/11] |
| Open interest BTC | 5,95 Md$ (5 marchés), 11,8 Md$ (Binance+Bybit+OKX), 41 Md$ (agrégé) : périmètres non comparables | [SOURCE TokenPost, AlertaChart, CoinStats] |
| Positionnement | 71 % de comptes longs, 29 % de comptes courts (26/11) : la foule reste longue malgré la peur | [SOURCE TokenPost 26/11] |
| Dominance BTC | ~58–60 % ; pic ~60,6 % le 12/11 | [SOURCE Crypto Briefing 24/11, Au79 27/11] |
| ETH | ~1 669–1 738 $, sous la résistance SuperTrend ~1 982 $ ; dominance ETH ~10 % | [SOURCE Au79 27/11, KuCoin] |
| Stablecoins | ~279,8 Md$ le 27/11, contre ~293 Md$ cités le 06/11 : possible contraction, mais méthodes différentes | [SOURCE Au79, Solcard] |
| Capitalisation totale | ~2,15–2,16 T$ | [SOURCE Au79, Analytics Insight] |
| Macro | Fed en pause, orientation restrictive ; probabilité d'une hausse en décembre évoquée mais **non confirmée** (pas d'accès FedWatch) | [SOURCE CryptoSlate, Cointelegraph — partiellement daté] |
| Narratif | « Revenus et rachats » : 13 des 15 tokens qui rachètent ont battu BTC en 2026. La corrélation n'est pas une causalité, comme le note la source elle-même | [SOURCE 24/7 Wall St. 09/11, KuCoin 12/11] |

**Lecture du régime [ESTIMATION].** Le marché est baissier et en aversion au risque, sans capitulation des dérivés : le funding n'est pas négatif et la foule reste longue. Les liquidités ne rentrent pas (sorties ETF, stablecoins stables ou en baisse) et la dominance BTC est élevée. Dans ce régime, les rebonds de retour à la moyenne sont plus probables que les tendances haussières durables. Le risque principal est une liquidation des longs encore nombreux. **Régime par défaut du système : `mean_reverting` dans une tendance baissière, avec `high_vol` et `crisis` fréquents.**

**Conséquence.** Les vraies configurations asymétriques à l'achat sont rares. J'ai retenu 5 finalistes : 2 à biais court, 1 pari d'événement, 1 long fondamental et BTC en retour à la moyenne. Je n'en ai pas fabriqué dix pour remplir le quota.

---

## 2. Finalistes

### 2.1 HYPE (Hyperliquid) — seul long fondamental

- **Thèse.** Le protocole a réalisé ~80,3 M$ de revenus sur 30 j pour ~105,7 M$ de frais [SOURCE DefiLlama, ~27/11]. La quasi-totalité des frais finance des rachats de HYPE (« 99 % » selon un article) [SOURCE AltcoinBuzz]. Les rachats 2026 atteignent ~791 M$ pour une offre circulante en hausse de seulement 0,43 % [SOURCE KuCoin 12/11]. Hyperliquid est 1er en revenus versés aux détenteurs sur 30 j au 24/11, avec 77,9 M$ [SOURCE Castle Labs]. La valeur revient bien au token, par les rachats.
- **Catalyseurs.**
  - Confirmé : déblocage de jusqu'à 9,92 M HYPE pour les contributeurs le 06/12, soit ~600 M$, **négatif** [SOURCE Crypto.com]. Les déblocages précédents ont été inférieurs au calendrier, selon la même source.
  - Spéculatif : poursuite de la rotation vers les tokens à revenus.
- **Cas baissier, construit agressivement.**
  1. Les revenus suivent le volume de perpétuels, qui est procyclique : un marché baissier calme les réduit. Le rendement des rachats baisse alors au pire moment.
  2. Le déblocage du 06/12 pèse ~7 fois les rachats mensuels [ESTIMATION : 600 M$ / ~80 M$]. Si les contributeurs vendent, les rachats ne compensent pas.
  3. La concentration des détenteurs et la part des initiés ne sont **pas vérifiées**.
  4. Risques de concurrence et de réglementation sur les perpétuels décentralisés.
  5. La surperformance 2026 (« +200 % » [SOURCE 24/7 Wall St.]) peut déjà intégrer la thèse : le catalyseur est en partie dans le prix [SPÉCULATION].
- **Invalidation.**
  - Revenus sur 30 j inférieurs à 50 M$ sur DefiLlama [ESTIMATION de seuil].
  - Offre circulante en hausse de plus de 2 % après le 06/12.
  - Rachats suspendus ou redirigés.
- **Manquant [NON VÉRIFIÉ].** TVL, utilisateurs actifs, concentration des détenteurs, calendrier complet des déblocages.

### 2.2 BTC — retour à la moyenne en peur extrême

- **Thèse [SPÉCULATION].** Des lectures de peur extrême (11) avec un funding neutre ont souvent précédé des rebonds courts. Rien ne démontre que ce soit le cas ici.
- **Catalyseurs.** Décision de la Fed en décembre, dans un sens ou dans l'autre [NON VÉRIFIÉ : date et probabilités]. Flux ETF.
- **Cas baissier.** La foule est longue à 71 %, donc le carburant d'une liquidation à la baisse est là. Les sorties ETF persistent. Une Fed restrictive ou une hausse surprise prolongerait la baisse.
- **Invalidation.** Clôture journalière sous le plus bas de novembre sans absorption, ou funding qui devient franchement négatif avec un OI en hausse (shorts agressifs qui gagnent). Dans les deux cas, désactiver les longs.

### 2.3 ETH — faiblesse relative, biais court

- **Thèse.** ETH est sous la résistance ~1 982 $ et sa dominance n'est que de ~10 %, alors que celle de BTC atteint 58–60 % [SOURCE Au79, KuCoin].
- **Cas baissier du short.** ETH est très survendu en relatif. Le moindre retour de l'appétit pour le risque déclenche des rachats de couverture violents.
- **Invalidation.** Reprise de 1 982 $ en clôture journalière et ratio ETH/BTC en hausse sur 2 semaines.
- **Manquant [NON VÉRIFIÉ].** Frais du L1, taux de combustion, émission nette.

### 2.4 PUMP — rachats sans accrétion, biais court

- **Thèse.** ~407 M$ de rachats en 2026, mais l'offre circulante a augmenté de 29,5 % [SOURCE KuCoin 12/11]. Les rachats ne compensent pas la dilution : la valeur **ne s'accumule pas** sur le token net de l'émission. Pump est 3e en revenus aux détenteurs sur 7 j [SOURCE DefiLlama 19/11]. Déblocage annoncé vers le 14/12, d'après une source unique [SOURCE DeFi Saver, à confirmer].
- **Cas baissier du short.** Les rachats restent réels et importants, et un short squeeze est possible sur un token à forte attention retail. Les frais d'emprunt et le funding sur un short peuvent coûter cher.
- **Invalidation.** Croissance de l'offre circulante inférieure à 5 % sur 90 j, ou annonce d'une combustion des tokens rachetés.

### 2.5 ENA (Ethena) — pari sur l'événement de déblocage

- **Fait.** Déblocage début décembre, mais les sources divergent : ~27,9 M$ le 01/12 [SOURCE Data Wallet] contre ~94,2 M$ le 02/12 [SOURCE DeFi Saver].
- **Thèse.** Aucune thèse fondamentale. On trade la réaction au déblocage, dans le sens du flux, avec un horizon court.
- **Cas baissier.** L'événement est connu et probablement déjà dans le prix. Les pertes viennent alors du spread et du slippage.
- **Invalidation.** Montant non confirmé par la documentation officielle d'Ethena avant le 01/12 : désactiver le schéma.

### 2.6 Écartés, avec la raison

| Actif | Raison de l'écart |
|---|---|
| DRV (Derive) | ~727 k$ de frais sur 30 j, dont 50 % en rachats [SOURCE Bankless via KuCoin]. Taille et liquidité trop faibles pour un agent automatisé : le slippage mangerait l'avantage [ESTIMATION]. À garder en liste de surveillance. |
| XRP | Libération d'escrow de 1 Md XRP le 01/12, dont ~700 M re-séquestrés en novembre [SOURCE Crypto.com, CoinTurk]. Événement mécanique, connu et récurrent : pas d'asymétrie. |
| AI tokens (FET, VIRTUAL, VVV) | Hausses de +7 % en intrajournalier sur des actualités NVIDIA [SOURCE KuCoin] : moteur narratif, pas fondamental. |
| AAVE, JUP | Données de rachats 2026 incomplètes dans mes sources. Pour Aave, ~45 M$ de rachats depuis avril 2025 sans performance [SOURCE Castle Labs, juillet] : à réévaluer. |

---

## 3. Schémas Jev compilés

Chaque finaliste est compilé en `schemas/<SYMBOL>.json`, généré par `fade_trader/finalists.py`. La commande `fade-trader compile-schemas` les régénère. Les cinq questions sont communes et évaluées en un seul appel :

| Clé | Type | Sortie |
|---|---|---|
| `regime` | choice | trending / mean_reverting / high_vol / crisis |
| `direction` | choice | long / short / neutral (l'énoncé porte le biais de la thèse) |
| `toxic_flow` | noul | probabilité 0..1 |
| `setup_quality` | score | 0..3 |
| `risk_state` | choice | safe / near_limit / reduce |

Le code fixe, pour chaque schéma, l'horizon, le rapport gain/risque et le stop [ESTIMATIONS initiales] :

| Schéma | Horizon | R:R | Stop |
|---|---|---|---|
| BTC | 60 min | 1,8 | 80 bps |
| ETH | 60 min | 1,8 | 100 bps |
| HYPE | 120 min | 2,0 | 150 bps |
| PUMP | 60 min | 1,6 | 200 bps |
| ENA | 30 min | 1,5 | 150 bps |

---

## Sources (consultées le 28/11/2026)

- TokenPost, instantané des contrats à terme, 26/11 : https://www.tokenpost.com/news/investing/63067 et 20/11 : https://www.tokenpost.com/news/investing/61963
- AlertaChart, dérivés crypto, 23/11 : https://www.alertachart.com/news/2026-11-23-crypto-derivatives-23-november-bitcoin-open-interest-down-2-1-in-coins-in-24-hours-d35374
- CoinStats, actualité BTC : https://coinstats.app/ai/a/latest-news-for-bitcoin
- Au79 Macro Research, 27/11 : https://martyau79.substack.com/p/27nov2026-crypto-and-macro-liquidity
- Crypto Briefing, dominance BTC : https://cryptobriefing.com/bitcoin-market-share-rises-59-percent/
- KuCoin, dominance : https://www.kucoin.com/news/flash/bitcoin-holds-57-88-of-total-crypto-market-cap-as-altcoins-struggle
- Solcard, capitalisation totale : https://www.solcard.cc/blog/total-crypto-market-cap
- Analytics Insight : https://www.analyticsinsight.net/price-analysis/crypto-price-today-global-market-cap-reaches-usd-216-trillion-as-bitcoin-and-ethereum-advance
- CryptoSlate, Fed : https://cryptoslate.com/december-fed-rate-cut-canceled-18-chance-of-hike-slowing-bitcoin-rally/
- DefiLlama, Hyperliquid : https://defillama.com/protocol/hyperliquid ; revenus aux détenteurs : https://defillama.com/holders-revenue ; calendrier : https://defillama.com/calendar
- Castle Labs, classement des revenus : https://castlelabs.io/research/crypto-revenue-rankings
- AltcoinBuzz, Hyperliquid : https://www.altcoinbuzz.io/hyperliquid-68-9m-revenue-hype-buybacks
- KuCoin, rachats 2026 HYPE / PUMP / AAVE / JUP : https://www.kucoin.com/blog/crypto-token-buybacks-token-inflation-2026
- 24/7 Wall St., rachats contre BTC, 09/11 : https://247wallst.com/investing/cryptocurrency/2026/11/09/13-of-15-cryptos-that-buy-back-their-own-tokens-beat-bitcoin-this-year-is-that-the-secret-behind-hyperliquids-200-gain/
- Crypto.com, décembre 2026 : https://crypto.com/us/market-updates/best-crypto-december-2026
- Data Wallet, calendrier des déblocages : https://www.datawallet.com/token-unlock-calendar
- Tokentoria, déblocages : https://tokentoria.com/en/unlocks/
- CoinTurk, escrow XRP : https://en.coin-turk.com/ripple-to-release-final-1-billion-xrp-escrow-of-2026-on-december-1/
- KuCoin, surperformance pendant la baisse : https://www.kucoin.com/news/flash/five-tokens-outperformed-bitcoin-in-ai-driven-two-week-sell-off
- KuCoin, tokens IA : https://www.kucoin.com/blog/en-why-did-ai-related-crypto-tokens-rally-over-7-intraday-as-bitcoin-lost-momentum
