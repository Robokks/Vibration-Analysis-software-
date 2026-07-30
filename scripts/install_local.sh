#!/usr/bin/env bash
# One-shot install: third-party deps (from requirements.txt) then all
# seven local packages in editable mode.
#
# Kept as a plain command list rather than baked into requirements.txt
# because older pip releases (e.g. the 23.2.x that ships with many
# Windows PyCharm bundles) reject `-e ./path` inside a requirements
# file with "is not a valid editable requirement".
#
# Run from the repository root inside your activated venv:
#   . .venv/bin/activate
#   scripts/install_local.sh
#
# Pass --dev to also install pytest via requirements-dev.txt.

set -euo pipefail

cd "$(dirname "$0")/.."

python -m pip install --upgrade pip

if [[ "${1:-}" == "--dev" ]]; then
    python -m pip install -r requirements-dev.txt
else
    python -m pip install -r requirements.txt
fi

python -m pip install \
    -e libs/nvh_contract \
    -e libs/nvh_api_schemas \
    -e design-tokens \
    -e analysis-engine \
    -e simulator \
    -e web-backend \
    -e qt-app

echo
echo "Local packages installed. Try:  nvh-sim --trials 5"
