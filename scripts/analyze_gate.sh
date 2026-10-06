#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 2 ]] || { echo "Usage: $0 RUNS_DIR ANALYSIS_DIR [METRIC]"; exit 2; }
RUNS=$(realpath "$1")
OUT=$(realpath -m "$2")
METRIC="${3:-post_min_planner_desired_speed}"
: "${CRADRIVE_ROOT:?set CRADRIVE_ROOT}"
mkdir -p "$OUT/figures"
cd "$CRADRIVE_ROOT"
python -m cradrive.analysis.summarize --runs "$RUNS" --out "$OUT"
python -m cradrive.analysis.audit_interventions --summary "$OUT/run_summary.csv" --out "$OUT/intervention_audit.csv"
python -m cradrive.analysis.curve_metrics --summary "$OUT/run_summary.csv" --audit "$OUT/intervention_audit.csv" --require-audit-pass --metric "$METRIC" --out "$OUT/curve_metrics.csv"
python -m cradrive.analysis.plot_curves --summary "$OUT/run_summary.csv" --audit "$OUT/intervention_audit.csv" --require-audit-pass --metric "$METRIC" --out "$OUT/figures"
python tools/validate_results.py --runs "$RUNS" | tee "$OUT/validate_results.txt"
echo "Analysis written to $OUT"
