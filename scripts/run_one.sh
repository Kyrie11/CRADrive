#!/usr/bin/env bash
set -euo pipefail
usage(){ echo "Usage: $0 tcp|simlingo|leadcvpr ROUTE_XML VARIANT_JSON OUT_DIR SEED [GPU_RANK]"; exit 2; }
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
    for f in trace.jsonl result.json stdout.log live_results.txt run_status.json scenario_meta.json run_provenance.json; do
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
# Route id is required by LEAD cvpr2026 ClosedLoopConfig in Bench2Drive mode.
ROUTE_ID=$(python - "$VARIANT_JSON" <<'PYROUTE'
import json,sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["route_id"])
PYROUTE
)
export BENCHMARK_ROUTE_ID="$ROUTE_ID"
export ROUTE_NUMBER="$ROUTE_ID"
PYTAG=$(python - <<'PYVER'
import sys
print(f"py{sys.version_info.major}.{sys.version_info.minor}")
PYVER
)
CARLA_EGG=$(ls "$CARLA_ROOT"/PythonAPI/carla/dist/carla-0.9.15-${PYTAG}-linux-x86_64.egg 2>/dev/null | head -n1 || true)
# LEAD cvpr2026 uses Python 3.10 and installs carla==0.9.15 from pip; older B2D/TCP
# environments may instead rely on a matching CARLA egg.  Never inject a py3.8 egg
# into a py3.10 process.
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
    UPSTREAM_REPO="$TCP_REPO"; UPSTREAM_CKPT="$TCP_CKPT"
    ;;
  simlingo)
    : "${SIMLINGO_REPO:?set SIMLINGO_REPO}"
    : "${SIMLINGO_CKPT:?set SIMLINGO_CKPT}"
    export PYTHONPATH="$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$SIMLINGO_REPO:$SIMLINGO_REPO/team_code:$PYTHONPATH"
    TEAM_AGENT="$CRADRIVE_ROOT/cradrive/agents/simlingo_cra_agent.py"
    TEAM_CONFIG="$SIMLINGO_CKPT"
    UPSTREAM_REPO="$SIMLINGO_REPO"; UPSTREAM_CKPT="$SIMLINGO_CKPT"
    ;;
  leadcvpr)
    : "${LEAD_CVPR_REPO:?set LEAD_CVPR_REPO to LEAD cvpr2026 checkout}"
    : "${LEAD_CVPR_CKPT:?set LEAD_CVPR_CKPT to a TFv6 checkpoint directory}"
    export LEAD_PROJECT_ROOT="${LEAD_PROJECT_ROOT:-$LEAD_CVPR_REPO}"
    export IS_BENCH2DRIVE=1
    # Paper-reproduction behavior.  Override LEAD_CLOSED_LOOP_CONFIG explicitly for
    # a post-processing ablation; the CRADrive adapter logs both planner target speed
    # and final executed control so the two can be separated in analysis.
    export LEAD_CLOSED_LOOP_CONFIG="${LEAD_CLOSED_LOOP_CONFIG:-sensor_agent_creeping=True use_kalman_filter=True slower_for_stop_sign=True}"
    export PYTHONPATH="$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$LEAD_CVPR_REPO:$PYTHONPATH"
    TEAM_AGENT="$CRADRIVE_ROOT/cradrive/agents/lead_cvpr_cra_agent.py"
    TEAM_CONFIG="$LEAD_CVPR_CKPT"
    UPSTREAM_REPO="$LEAD_CVPR_REPO"; UPSTREAM_CKPT="$LEAD_CVPR_CKPT"
    ;;
  *) usage;;
esac

# Record enough provenance to make every scientific run auditable after the output
# directory is copied to another machine.  Git failures are tolerated for unpacked
# source trees.
export CRADRIVE_UPSTREAM_REPO="$UPSTREAM_REPO"
export CRADRIVE_UPSTREAM_CKPT="$UPSTREAM_CKPT"
python - "$OUT_DIR/run_provenance.json" "$ROUTE_XML" "$VARIANT_JSON" <<'PYPROV'
import hashlib,json,os,platform,subprocess,sys,time
from pathlib import Path
def sha256(p):
    h=hashlib.sha256(); h.update(Path(p).read_bytes()); return h.hexdigest()
def git_head(repo):
    try: return subprocess.check_output(["git","-C",repo,"rev-parse","HEAD"],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return None
out,route,variant=sys.argv[1:]
obj={
    "created_at_unix":time.time(),
    "python":sys.version,
    "platform":platform.platform(),
    "agent":os.environ.get("CRADRIVE_RUN_ID","").split("_",1)[0],
    "run_id":os.environ.get("CRADRIVE_RUN_ID"),
    "seed":os.environ.get("CRADRIVE_SEED"),
    "route_xml":str(Path(route).resolve()),"route_sha256":sha256(route),
    "variant_json":str(Path(variant).resolve()),"variant_sha256":sha256(variant),
    "cradrive_git":git_head(os.environ.get("CRADRIVE_ROOT","")),
    "upstream_repo":os.environ.get("CRADRIVE_UPSTREAM_REPO"),
    "upstream_git":git_head(os.environ.get("CRADRIVE_UPSTREAM_REPO","")),
    "upstream_checkpoint":os.environ.get("CRADRIVE_UPSTREAM_CKPT"),
    "lead_closed_loop_config":os.environ.get("LEAD_CLOSED_LOOP_CONFIG"),
}
Path(out).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
PYPROV

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
