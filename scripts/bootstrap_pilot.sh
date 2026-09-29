#!/usr/bin/env bash
set -euo pipefail

: "${CRADRIVE:?export CRADRIVE=/path/to/CRADrive}"
: "${B2D_ROOT:?export B2D_ROOT=/path/to/Bench2Drive-0.0.4}"
: "${DT_ROOT:?export DT_ROOT=/path/to/DriveTransformer}"
: "${CARLA_ROOT:?export CARLA_ROOT=/path/to/CARLA_0.9.15}"
: "${DT_CONFIG:?export DT_CONFIG=/path/to/drivetransformer_large.py}"
: "${DT_CKPT:?export DT_CKPT=/path/to/drivetransformer_large.pth}"
EXP_ROOT="${EXP_ROOT:-$CRADRIVE/experiments/pilot_dt}"

python "$CRADRIVE/scripts/validate_setup.py" \
  --bench2drive "$B2D_ROOT" --drivetransformer "$DT_ROOT" --carla "$CARLA_ROOT" \
  --config "$DT_CONFIG" --checkpoint "$DT_CKPT"

python "$CRADRIVE/scripts/preflight_runtime.py" \
  --bench2drive "$B2D_ROOT" --drivetransformer "$DT_ROOT" --carla "$CARLA_ROOT"

python "$CRADRIVE/scripts/apply_b2d_patch.py" --bench2drive "$B2D_ROOT"

mkdir -p "$EXP_ROOT"
python "$CRADRIVE/scripts/generate_pilot.py" \
  --routes "$B2D_ROOT/leaderboard/data/bench2drive_0.0.4_val.xml" \
  --config "$CRADRIVE/configs/pilot.json" \
  --out "$EXP_ROOT"

echo "Bootstrap complete: $EXP_ROOT/manifest.json"
