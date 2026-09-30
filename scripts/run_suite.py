#!/usr/bin/env python3
import argparse, json, os, subprocess
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--agent", choices=["tcp","simlingo"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--gpu-rank", default="0")
    ap.add_argument("--families", default="", help="comma-separated filter")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    args=ap.parse_args()
    root=Path(os.environ["CRADRIVE_ROOT"])
    run_one=root/"scripts/run_one.sh"
    rows=[json.loads(x) for x in open(args.manifest, encoding="utf-8") if x.strip()]
    fams={x for x in args.families.split(',') if x}
    if fams: rows=[r for r in rows if r['family'] in fams]
    seeds=[int(x) for x in args.seeds.split(',') if x]
    for r in rows:
        for seed in seeds:
            od=Path(args.out)/args.agent/r['family']/f"route_{r['route_id']}"/r['variant']/f"seed_{seed}"
            if args.skip_existing and (od/"result.json").exists() and (od/"trace.jsonl").exists():
                print("SKIP", od); continue
            cmd=[str(run_one),args.agent,r['route_xml'],r['variant_json'],str(od),str(seed),str(args.gpu_rank)]
            print("RUN", ' '.join(cmd), flush=True)
            if not args.dry_run:
                od.mkdir(parents=True, exist_ok=True)
                rc=subprocess.call(cmd, env=os.environ.copy())
                if rc != 0: print(f"WARN rc={rc}: {od}", flush=True)
if __name__=="__main__": main()
