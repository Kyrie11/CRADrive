#!/usr/bin/env bash
set -euo pipefail
: "${CRADRIVE:?}"
EXP_ROOT="${EXP_ROOT:-$CRADRIVE/experiments/pilot_dt}"
python "$CRADRIVE/scripts/analyze_pilot.py" \
  --manifest "$EXP_ROOT/manifest.json" \
  --runs "$EXP_ROOT/runs" \
  --out "$EXP_ROOT/analysis"

echo "Open: $EXP_ROOT/analysis/report.md"
echo "CSV:  $EXP_ROOT/analysis/summary.csv"
