#!/usr/bin/env bash

set -euo pipefail

readme="profile/README.md"
stats_svg="profile/assets/github-stats-card.svg"
langs_svg="profile/assets/top-langs-card.svg"

if grep -q 'github-readme-stats\.vercel\.app' "$readme"; then
  echo "README still references github-readme-stats.vercel.app"
  exit 1
fi

for ref in "./assets/github-stats-card.svg" "./assets/top-langs-card.svg"; do
  if ! grep -q "$ref" "$readme"; then
    echo "README is missing expected local asset reference: $ref"
    exit 1
  fi
done

for svg in "$stats_svg" "$langs_svg"; do
  if [[ ! -f "$svg" ]]; then
    echo "Missing SVG asset: $svg"
    exit 1
  fi
done

python3 - <<'PY'
import xml.etree.ElementTree as ET

for path in (
    "profile/assets/github-stats-card.svg",
    "profile/assets/top-langs-card.svg",
):
    ET.parse(path)
print("README profile assets verified")
PY
