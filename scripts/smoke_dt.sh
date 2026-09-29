#!/usr/bin/env bash
set -euo pipefail
: "${CRADRIVE:?}"; : "${B2D_ROOT:?}"; : "${DT_ROOT:?}"; : "${CARLA_ROOT:?}"; : "${DT_CONFIG:?}"; : "${DT_CKPT:?}"
EXP_ROOT="${EXP_ROOT:-$CRADRIVE/experiments/pilot_dt}"
GPU="${GPU:-0}"
python "$CRADRIVE/scripts/run_grid.py" \
  --manifest "$EXP_ROOT/manifest.json" \
  --bench2drive "$B2D_ROOT" --drivetransformer "$DT_ROOT" --carla "$CARLA_ROOT" \
  --dt-config "$DT_CONFIG" --dt-checkpoint "$DT_CKPT" \
  --out "$EXP_ROOT/runs" --gpu "$GPU" \
  --experiment dynamic_crossing_reaction_time --kind causal --max-runs 1 \
  --save-images-every 10
