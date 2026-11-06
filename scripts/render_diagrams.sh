#!/usr/bin/env bash
# Regenera labs/VXX/diagrama.svg a partir de labs/VXX/diagrama.mmd (requiere Node/npx y Chrome para puppeteer).
set -euo pipefail
cd "$(dirname "$0")/.."
cfg=$(mktemp); echo '{"args":["--no-sandbox"]}' > "$cfg"
cfgm=$(mktemp); echo '{"htmlLabels":false,"flowchart":{"htmlLabels":false}}' > "$cfgm"
for mmd in labs/V*/diagrama.mmd; do
  npx -y @mermaid-js/mermaid-cli -p "$cfg" -c "$cfgm" -i "$mmd" -o "${mmd%.mmd}.svg" -b white
done
