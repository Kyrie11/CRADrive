#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 tcp|simlingo ROUTE_XML VARIANT_JSON OUT_DIR SEED [GPU_RANK]"; exit 2; }
[[ $# -ge 5 ]] || usage
AGENT="$1"; ROUTE_XML=$(realpath "$2"); VARIANT_JSON=$(realpath "$3"); OUT_DIR=$(realpath -m "$4"); SEED="$5"; GPU_RANK="${6:-0}"
: "${CRADRIVE_ROOT:?set CRADRIVE_ROOT}"
: "${B2D_ROOT:?set B2D_ROOT}"
: "${CARLA_ROOT:?set CARLA_ROOT}"
mkdir -p "$OUT_DIR" "$OUT_DIR/viz"

export SCENARIO_RUNNER_ROOT="$B2D_ROOT/scenario_runner"
export LEADERBOARD_ROOT="$B2D_ROOT/leaderboard"
export ROUTES="$ROUTE_XML"
export CRADRIVE_VARIANT_JSON="$VARIANT_JSON"
export CRADRIVE_TRACE_PATH="$OUT_DIR/trace.jsonl"
export SAVE_PATH="$OUT_DIR/viz/"
# Keep Bench2Drive 0.0.4 ahead of SimLingo's bundled Bench2Drive 0.0.3.
CARLA_EGG=$(ls "$CARLA_ROOT"/PythonAPI/carla/dist/carla-0.9.15-py3.8-linux-x86_64.egg 2>/dev/null | head -n1 || true)
export PYTHONPATH="$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$CARLA_ROOT/PythonAPI:$CARLA_ROOT/PythonAPI/carla${CARLA_EGG:+:$CARLA_EGG}:${PYTHONPATH:-}"

EVAL="$B2D_ROOT/leaderboard/leaderboard/leaderboard_evaluator.py"
RESULT="$OUT_DIR/result.json"
DEBUG_RESULT="$OUT_DIR/live_results.txt"

case "$AGENT" in
  tcp)
    : "${TCP_REPO:?set TCP_REPO}"
    : "${TCP_CKPT:?set TCP_CKPT}"
    export IS_BENCH2DRIVE=1
    export PLANNER_TYPE="${PLANNER_TYPE:-only_traj}"
    export PYTHONPATH="$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$TCP_REPO:$TCP_REPO/team_code:$PYTHONPATH"
    TEAM_AGENT="$CRADRIVE_ROOT/cradrive/agents/tcp_cra_agent.py"
    TEAM_CONFIG="$TCP_CKPT"
    WORKDIR="$TCP_REPO"
    ;;
  simlingo)
    : "${SIMLINGO_REPO:?set SIMLINGO_REPO}"
    : "${SIMLINGO_CKPT:?set SIMLINGO_CKPT}"
    export PYTHONPATH="$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$SIMLINGO_REPO:$SIMLINGO_REPO/team_code:$PYTHONPATH"
    TEAM_AGENT="$CRADRIVE_ROOT/cradrive/agents/simlingo_cra_agent.py"
    TEAM_CONFIG="$SIMLINGO_CKPT"
    WORKDIR="$SIMLINGO_REPO"
    ;;
  *) usage;;
esac

cd "$WORKDIR"
python -u "$EVAL" \
  --routes="$ROUTE_XML" \
  --repetitions=1 \
  --track=SENSORS \
  --checkpoint="$RESULT" \
  --debug-checkpoint="$DEBUG_RESULT" \
  --timeout=600 \
  --agent="$TEAM_AGENT" \
  --agent-config="$TEAM_CONFIG" \
  --traffic-manager-seed="$SEED" \
  --gpu-rank="$GPU_RANK" \
  2>&1 | tee "$OUT_DIR/stdout.log"
