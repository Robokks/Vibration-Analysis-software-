#!/usr/bin/env bash
# Detects and cleans up per-subfolder `.venv/` directories that a
# project-aware IDE sometimes auto-creates alongside each
# sub-package's `pyproject.toml`. See fix_pycharm.bat for the
# full explanation of the failure mode.

set -euo pipefail

cd "$(dirname "$0")/.."

SUBS=(libs/nvh_contract libs/nvh_api_schemas design-tokens
      analysis-engine simulator web-backend qt-app)

STRAY=()
for d in "${SUBS[@]}"; do
    if [[ -d "$d/.venv" ]]; then
        STRAY+=("$d/.venv")
    fi
done

if [[ ${#STRAY[@]} -eq 0 ]]; then
    echo "No stray per-subfolder venvs found. Nothing to do."
    echo
    echo "Make sure your IDE's Python interpreter points at the ROOT venv:"
    echo "  $PWD/.venv/bin/python"
    exit 0
fi

echo "Found stray per-subfolder venvs:"
printf '  %s\n' "${STRAY[@]}"
echo
read -r -p "Delete them [y/N]? " ANSWER
if [[ "$ANSWER" != "y" && "$ANSWER" != "Y" ]]; then
    echo "Aborted -- nothing deleted."
    exit 0
fi

for v in "${STRAY[@]}"; do
    echo "Removing $v ..."
    rm -rf "$v"
done

echo
echo "Done. Point your IDE at the root interpreter:"
echo "  $PWD/.venv/bin/python"
