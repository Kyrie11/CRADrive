#!/usr/bin/env python3
import argparse, json, os, subprocess
from pathlib import Path


def completed_run(od: Path) -> bool:
    """Skip only a genuinely finished run, never a stale Started checkpoint."""
    st = od / "run_status.json"
    trace = od / "trace.jsonl"
    log = od / "stdout.log"
    if not (st.exists() and trace.exists() and log.exists()):
        return False
    try:
        status = json.load(open(st, encoding="utf-8"))
    except Exception:
        return False
    if not status.get("runner_finished") or int(status.get("exit_code", 1)) != 0:
        return False
    # A completed CARLA route prints this after criteria evaluation. This accepts a
    # route-level FAILURE (e.g. low speed) as a scientifically completed episode.
    txt = log.read_text(encoding="utf-8", errors="replace")
    return "Registering the route statistics" in txt


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--agent", choices=["tcp","simlingo"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gpu-rank", default="0")
    ap.add_argument("--families", default="", help="comma-separated family filter")
    ap.add_argument("--route-ids", default="", help="comma-separated route-id filter")
    ap.add_argument("--variants", default="", help="comma-separated variant-label filter")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-existing", action="store_true", help="skip only completed runs")
    args=ap.parse_args()
    root=Path(os.environ["CRADRIVE_ROOT"])
    run_one=root/"scripts/run_one.sh"
    rows=[json.loads(x) for x in open(args.manifest, encoding="utf-8") if x.strip()]
    fams={x for x in args.families.split(',') if x}
    route_ids={x for x in args.route_ids.split(',') if x}
    variants={x for x in args.variants.split(',') if x}
    if fams: rows=[r for r in rows if r['family'] in fams]
    if route_ids: rows=[r for r in rows if str(r['route_id']) in route_ids]
    if variants: rows=[r for r in rows if r['variant'] in variants]
    seeds=[int(x) for x in args.seeds.split(',') if x]
    for r in rows:
        for seed in seeds:
            od=Path(args.out)/args.agent/r['family']/f"route_{r['route_id']}"/r['variant']/f"seed_{seed}"
            if args.skip_existing and completed_run(od):
                print("SKIP completed", od); continue
            cmd=[str(run_one),args.agent,r['route_xml'],r['variant_json'],str(od),str(seed),str(args.gpu_rank)]
            print("RUN", ' '.join(cmd), flush=True)
            if not args.dry_run:
                od.mkdir(parents=True, exist_ok=True)
                rc=subprocess.call(cmd, env=os.environ.copy())
                if rc != 0: print(f"WARN rc={rc}: {od}", flush=True)
if __name__=="__main__": main()
