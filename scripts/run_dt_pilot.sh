#!/usr/bin/env bash
set -euo pipefail
: "${CRADRIVE:?}"; : "${B2D_ROOT:?}"; : "${DT_ROOT:?}"; : "${CARLA_ROOT:?}"; : "${DT_CONFIG:?}"; : "${DT_CKPT:?}"
EXP_ROOT="${EXP_ROOT:-$CRADRIVE/experiments/pilot_dt}"
GPU="${GPU:-0}"
COMMON=(
  --manifest "$EXP_ROOT/manifest.json"
  --bench2drive "$B2D_ROOT"
  --drivetransformer "$DT_ROOT"
  --carla "$CARLA_ROOT"
  --dt-config "$DT_CONFIG"
  --dt-checkpoint "$DT_CKPT"
  --out "$EXP_ROOT/runs"
  --gpu "$GPU"
)

python "$CRADRIVE/scripts/run_grid.py" "${COMMON[@]}" --experiment dynamic_crossing_reaction_time --kind causal
python "$CRADRIVE/scripts/run_grid.py" "${COMMON[@]}" --experiment parking_crossing_reaction_time --kind causal
python "$CRADRIVE/scripts/run_grid.py" "${COMMON[@]}" --kind nuisance_weather
