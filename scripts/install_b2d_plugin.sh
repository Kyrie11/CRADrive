#!/usr/bin/env bash
set -euo pipefail
: "${CRADRIVE_ROOT:?set CRADRIVE_ROOT}"
: "${B2D_ROOT:?set B2D_ROOT}"
SRC="$CRADRIVE_ROOT/cradrive/scenarios/cra_interventions.py"
DST="$B2D_ROOT/scenario_runner/srunner/scenarios/cra_interventions.py"
cp "$SRC" "$DST"
echo "Installed $DST"
python -m py_compile "$DST"
