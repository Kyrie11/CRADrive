#!/usr/bin/env python3
"""Summarize CRADrive traces and diagnose monotonicity / delayed response."""
import argparse, csv, json, math
from pathlib import Path
from statistics import mean


def load_trace(path):
    return [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]


def desired_speed(r):
    mo=r.get("model_output") or {}
    x=mo.get("planner_desired_speed")
    return float(x) if x is not None else None


def nearest_actor(r):
    acts=r.get("scenario_actors") or []
    return acts[0] if acts else None


def summarize_trace(path):
    rows=load_trace(path)
    if not rows: return None
    # Focus on frames where a scenario actor is within 45m, plus all action frames if none.
    active=[]
    for r in rows:
        a=nearest_actor(r)
        if a and a.get("distance",1e9) <= 45.0:
            active.append(r)
    if not active: active=rows
    ds=[desired_speed(r) for r in active if desired_speed(r) is not None]
    speeds=[r["ego"]["speed"] for r in active if r.get("ego")]
    dists=[]; ttcs=[]; closings=[]
    for r in active:
        a=nearest_actor(r)
        if a:
            dists.append(a["distance"])
            if a.get("ttc_longitudinal") is not None: ttcs.append(a["ttc_longitudinal"])
            closings.append(a["closing_speed"])
    first_t=active[0]["timestamp"]
    brake_ts=[r["timestamp"] for r in active if float(r["control"]["brake"]) > 0.5]
    meta=rows[0].get("variant") or {}
    return {
        "trace":str(path), "agent":rows[0].get("agent"), "family":meta.get("family"),
        "route_id":meta.get("route_id"), "variant":meta.get("variant"),
        "risk_rank":meta.get("risk_rank"), "n_frames":len(rows), "n_active":len(active),
        "min_planner_desired_speed":min(ds) if ds else None,
        "mean_planner_desired_speed":mean(ds) if ds else None,
        "min_ego_speed":min(speeds) if speeds else None,
        "min_actor_distance":min(dists) if dists else None,
        "min_realized_ttc":min(ttcs) if ttcs else None,
        "max_closing_speed":max(closings) if closings else None,
        "brake_latency_from_45m":(min(brake_ts)-first_t) if brake_ts else None,
        "ever_braked":bool(brake_ts),
    }


def monotonic_violations(group):
    # Higher risk_rank should not yield a *higher* minimum desired speed.
    pts=[(int(r['risk_rank']),r['min_planner_desired_speed']) for r in group if r['risk_rank'] is not None and r['min_planner_desired_speed'] is not None]
    pts=sorted(pts)
    violations=[]
    for i in range(len(pts)-1):
        if pts[i+1][1] > pts[i][1] + 0.25:  # 0.25 m/s tolerance
            violations.append((pts[i],pts[i+1]))
    return violations


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--runs",required=True); ap.add_argument("--out",required=True); args=ap.parse_args()
    traces=list(Path(args.runs).rglob("trace.jsonl"))
    summaries=[s for p in traces if (s:=summarize_trace(p))]
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    if not summaries:
        print("No traces found"); return
    fields=list(summaries[0].keys())
    with open(out/"run_summary.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(summaries)
    groups={}
    for s in summaries:
        if s['family'] == 'pedestrian_direction_control': continue
        # seed is implicit in trace path; analyze each route/agent/seed separately
        seed=next((x for x in Path(s['trace']).parts if x.startswith('seed_')), 'seed_unknown')
        groups.setdefault((s['agent'],s['family'],s['route_id'],seed),[]).append(s)
    report=[]
    total=0; bad=0
    for key,g in sorted(groups.items()):
        if len(g)<2: continue
        total+=1; v=monotonic_violations(g)
        if v: bad+=1
        report.append({"group":key,"n":len(g),"violations":v})
    json.dump(report,open(out/"monotonicity_report.json","w"),indent=2)
    print(f"traces={len(summaries)} groups={total} groups_with_nonmonotonicity={bad}")
    print(out/"run_summary.csv")
    print(out/"monotonicity_report.json")
if __name__=="__main__": main()
