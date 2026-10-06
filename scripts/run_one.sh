#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 tcp|simlingo ROUTE_XML VARIANT_JSON OUT_DIR SEED [GPU_RANK]"; exit 2; }
[[ $# -ge 5 ]] || usage
AGENT="$1"; ROUTE_XML=$(realpath "$2"); VARIANT_JSON=$(realpath "$3"); OUT_DIR=$(realpath -m "$4"); SEED="$5"; GPU_RANK="${6:-0}"
: "${CRADRIVE_ROOT:?set CRADRIVE_ROOT}"
: "${B2D_ROOT:?set B2D_ROOT}"
: "${CARLA_ROOT:?set CARLA_ROOT}"
mkdir -p "$OUT_DIR" "$OUT_DIR/viz"

# One writer per output directory. The old script reused trace.jsonl in append mode,
# so two evaluator processes could silently interleave records.
exec 9>"$OUT_DIR/.run.lock"
if command -v flock >/dev/null 2>&1; then
  flock -n 9 || { echo "ERROR: another run owns $OUT_DIR" >&2; exit 75; }
fi

RUN_ID="${CRADRIVE_RUN_ID:-${AGENT}_$(date +%Y%m%dT%H%M%S)_$$_s${SEED}}"
export CRADRIVE_RUN_ID="$RUN_ID"
export CRADRIVE_SEED="$SEED"

# Never append a new evaluation to stale scientific artifacts. Preserve old files
# for debugging unless CRADRIVE_KEEP_OLD=0.
if [[ -e "$OUT_DIR/trace.jsonl" || -e "$OUT_DIR/result.json" || -e "$OUT_DIR/stdout.log" ]]; then
  if [[ "${CRADRIVE_KEEP_OLD:-1}" == "1" ]]; then
    ARCHIVE="$OUT_DIR/_previous/$(date +%Y%m%dT%H%M%S)_$$"
    mkdir -p "$ARCHIVE"
    for f in trace.jsonl result.json stdout.log live_results.txt run_status.json scenario_meta.json; do
      [[ -e "$OUT_DIR/$f" ]] && mv "$OUT_DIR/$f" "$ARCHIVE/$f"
    done
  else
    rm -f "$OUT_DIR/trace.jsonl" "$OUT_DIR/result.json" "$OUT_DIR/stdout.log" "$OUT_DIR/live_results.txt" "$OUT_DIR/run_status.json" "$OUT_DIR/scenario_meta.json"
  fi
fi

export SCENARIO_RUNNER_ROOT="$B2D_ROOT/scenario_runner"
export LEADERBOARD_ROOT="$B2D_ROOT/leaderboard"
export ROUTES="$ROUTE_XML"
export CRADRIVE_VARIANT_JSON="$VARIANT_JSON"
export CRADRIVE_TRACE_PATH="$OUT_DIR/trace.jsonl"
export CRADRIVE_SCENARIO_META_PATH="$OUT_DIR/scenario_meta.json"
export SAVE_PATH="$OUT_DIR/viz/"
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
    ;;
  simlingo)
    : "${SIMLINGO_REPO:?set SIMLINGO_REPO}"
    : "${SIMLINGO_CKPT:?set SIMLINGO_CKPT}"
    export PYTHONPATH="$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$SIMLINGO_REPO:$SIMLINGO_REPO/team_code:$PYTHONPATH"
    TEAM_AGENT="$CRADRIVE_ROOT/cradrive/agents/simlingo_cra_agent.py"
    TEAM_CONFIG="$SIMLINGO_CKPT"
    ;;
  *) usage;;
esac

write_status() {
  local rc="$1"
  python - "$OUT_DIR/run_status.json" "$RUN_ID" "$AGENT" "$SEED" "$rc" <<'PY'
import json, os, sys, time
path, run_id, agent, seed, rc = sys.argv[1:]
obj = {"run_id": run_id, "agent": agent, "seed": int(seed), "exit_code": int(rc),
       "runner_finished": True, "ended_at_unix": time.time()}
with open(path, "w", encoding="utf-8") as f: json.dump(obj, f, indent=2)
PY
}

cd "$B2D_ROOT"
set +e
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
RC=${PIPESTATUS[0]}
set -e
write_status "$RC"
exit "$RC"
