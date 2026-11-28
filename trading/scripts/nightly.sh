#!/usr/bin/env bash
# Revue de nuit : à planifier hors séance, p. ex. cron `17 2 * * *`.
# Produit rapports + candidats dans state/review/<SYMBOL>/. Ne promeut RIEN :
# la promotion reste `fade-trader promote` (porte opérateur).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p state/review
JOURNAL="${1:-state/journal.jsonl}"
BRAIN_FLAG="${BRAIN:+--brain}"
for f in schemas/*.json; do
  sym="$(basename "$f" .json)"
  python3 -m fade_trader.cli nightly --symbol "$sym" --journal "$JOURNAL" $BRAIN_FLAG \
    > "state/review/${sym}.latest.json" 2>&1 || echo "revue $sym en échec" >&2
done
