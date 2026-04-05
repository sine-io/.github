#!/usr/bin/env bash

set -euo pipefail

readme="profile/README.md"
stats_svg="profile/assets/github-stats-card.svg"
langs_svg="profile/assets/top-langs-card.svg"
update_script="scripts/update_profile_cards.py"
workflow=".github/workflows/update-profile-cards.yml"

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

for required in "$update_script" "$workflow"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing automation file: $required"
    exit 1
  fi
done

if ! grep -q 'workflow_dispatch:' "$workflow"; then
  echo "Workflow is missing workflow_dispatch trigger"
  exit 1
fi

if ! grep -q 'schedule:' "$workflow"; then
  echo "Workflow is missing schedule trigger"
  exit 1
fi

if ! grep -q 'contents: write' "$workflow"; then
  echo "Workflow is missing contents: write permission"
  exit 1
fi

python3 - <<'PY'
import xml.etree.ElementTree as ET

for path in (
    "profile/assets/github-stats-card.svg",
    "profile/assets/top-langs-card.svg",
):
    ET.parse(path)
print("README profile assets verified")
PY
