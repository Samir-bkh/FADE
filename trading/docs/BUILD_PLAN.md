# Plan de construction en 6 phases, avec portes d'approbation

**À propos d'AgenKit.** Je n'ai pas pu vérifier `agenkit.xyz`. Le domaine n'apparaît dans aucun index de recherche, et le conteneur n'a pas pu le joindre. Les résultats les plus proches sont d'autres produits : « Engineer Kit » sur agentkit.best, et plusieurs projets open source nommés agentkit. Je ne recommande donc pas d'installer un outil que je n'ai pas pu identifier, qui se ferait de plus confier un système qui manipule de l'argent.

Le plan ci-dessous ne dépend d'aucun outil. Chaque phase a :

- des livrables aux chemins exacts ;
- un critère de sortie mesurable ;
- une **porte** que seul l'opérateur franchit.

Si l'opérateur confirme qu'AgenKit est l'outil voulu, ses six phases (spécification, architecture, plan, construction test-first, revue, livraison) correspondent une à une à celles-ci.

Statut : ✅ fait dans ce dépôt · 🔶 partiel · ⬜ à faire.

---

## Phase 1 — Spécification ✅

| Livrable | Chemin |
|---|---|
| Recherche, régime et finalistes | `trading/docs/RESEARCH.md` |
| Politique de risque et invariants | `trading/README.md` § Risque |
| Ce plan | `trading/docs/BUILD_PLAN.md` |

**Porte 1.** L'opérateur valide les finalistes, les limites dures et l'enveloppe de capital du papier.

## Phase 2 — Architecture ✅ / 🔶

| Livrable | Chemin |
|---|---|
| Types et convention causale | `trading/fade_trader/types.py` |
| Séparation cerveau / réflexe / code | `trading/README.md` § Architecture |
| Contrat Jev, isolé dans `TypeSafeWire` | `trading/fade_trader/jev.py` |

🔶 **Bloquant avant la phase 5.** Le format filaire Jev doit être confronté à `docs.typesafe.ai` : endpoint, ID de modèle et forme exacte de `answers`. Les sources tierces divergent sur ces trois points. Ajouter un test de contrat sur une réponse réelle enregistrée : `trading/tests/fixtures/jev_response.json`.

**Porte 2.** Le test de contrat Jev passe sur une réponse réelle.

## Phase 3 — Plan détaillé ✅

| Livrable | Chemin |
|---|---|
| Découpage en modules | `fade_trader/{state_engine,jev,policy,risk,escalation,execution,agent,review,cli}.py` |
| Commandes opérateur | `fade_trader/cli.py` |

**Porte 3.** Revue du découpage par l'opérateur.

## Phase 4 — Construction test-first ✅ / 🔶

| Livrable | Chemin |
|---|---|
| Moteur d'état causal, instantané < 400 tokens | `fade_trader/state_engine.py` |
| Risque dur et kill switch | `fade_trader/risk.py` |
| Filtres et quart de Kelly | `fade_trader/policy.py` |
| Escalade Opus 5.5, restrictive seulement | `fade_trader/escalation.py` |
| Courtier papier (frais et slippage) | `fade_trader/execution.py` |
| Boucle et journal JSONL | `fade_trader/agent.py` |
| Revue de nuit (Brier, PAV, ombre) | `fade_trader/review.py` |
| Tests (26, tous verts) | `tests/test_core.py` |

⬜ **À ajouter :**

| Élément | Chemin prévu | Détail |
|---|---|---|
| Flux de marché réel | `fade_trader/feeds/<exchange>.py` | Websocket du carnet et des trades. Horodatage de réception local, rejet des événements hors d'ordre. |
| Collecteur de contexte | `fade_trader/feeds/context.py` | Funding, OI, déblocages, revenus DefiLlama. Chaque point avec son instant de disponibilité. |
| Rejeu historique | `fade_trader/replay.py` | Même chemin de code que le direct. Frais et slippage réels du site visé. |

**Porte 4.** Rejeu sur au moins 90 jours d'historique, coûts inclus, avec un rapport de revue de nuit. Le Brier skill score de la direction doit être positif hors échantillon. Sinon, **pas de phase 5**.

## Phase 5 — Revue et papier en direct ⬜

| Élément | Chemin | Détail |
|---|---|---|
| Papier en direct | `fade-trader live --paper` | À câbler sur le flux réel, 4 semaines minimum. |
| Adaptateur d'exchange | `fade_trader/execution_<exchange>.py` | Ordres reduce-only natifs, sous-comptes, clé API **sans droit de retrait**. |
| Audit externe de `risk.py` | — | Une personne qui n'a pas écrit le code. |
| `/security-review` | — | Sur la gestion des clés. |

**Porte 5.** Les quatre conditions suivantes :

1. Slippage réel mesuré inférieur ou égal à l'hypothèse de `PolicyConfig.roundtrip_cost_bps`.
2. Brier skill score positif.
3. Aucune violation d'invariant dans le journal.
4. Signature de l'opérateur.

## Phase 6 — Livraison ⬜

| Élément | Détail |
|---|---|
| Capital réel | Mise en route à 10 % de l'enveloppe, puis montée par paliers hebdomadaires si les métriques tiennent. |
| Variables obligatoires | `FADE_LIVE_ACK=je-comprends-le-risque`, `TYPESAFE_API_KEY`, `ANTHROPIC_API_KEY`. |
| Planification | `scripts/nightly.sh` lancé chaque nuit (cron). Promotion via `fade-trader promote` uniquement. |

**Porte 6 (permanente).** Chaque promotion de schéma reste un geste opérateur. L'automatisation ne fait que proposer.
