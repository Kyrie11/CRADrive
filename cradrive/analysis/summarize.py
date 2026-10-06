#!/usr/bin/env python3
"""Summarize CRADrive traces with integrity and event-window checks.

Key principle: do not turn a partial/mixed trace into a scientific curve. The script
keeps diagnostic rows for every trace but marks invalid/unfinished runs explicitly.
By default monotonicity statistics use only trace_valid + route_evaluated runs.
"""
import argparse
import csv
import json
import math
import re
from pathlib import Path
from statistics import mean, median


def load_trace(path):
    rows=[]
    with open(path, encoding="utf-8") as f:
        for lineno, x in enumerate(f, 1):
            if not x.strip():
                continue
            try:
                rows.append(json.loads(x))
            except Exception as exc:
                raise ValueError(f"invalid JSON at {path}:{lineno}: {exc}")
    return rows


def desired_speed(r):
    mo=r.get("model_output") or {}
    x=mo.get("planner_desired_speed")
    try: return float(x) if x is not None else None
    except Exception: return None


def _actor_geometry(r, a):
    """Return distance_2d, relative_z, tcpa_2d, dcpa_2d, with legacy fallback."""
    d2=a.get("distance_2d")
    rz=a.get("relative_z")
    tcpa=a.get("tcpa_2d")
    dcpa=a.get("dcpa_2d")
    ego=r.get("ego") or {}
    try:
        el=ego.get("location") or [0,0,0]
        al=a.get("location") or [0,0,0]
        dx,dy,dz=float(al[0])-float(el[0]),float(al[1])-float(el[1]),float(al[2])-float(el[2])
        if d2 is None: d2=math.hypot(dx,dy)
        if rz is None: rz=dz
        if tcpa is None or dcpa is None:
            ev=ego.get("velocity") or [0,0,0]
            av=a.get("velocity") or [0,0,0]
            rvx,rvy=float(av[0])-float(ev[0]),float(av[1])-float(ev[1])
            den=rvx*rvx+rvy*rvy
            if den > 1e-8:
                t=max(0.0,-(dx*rvx+dy*rvy)/den)
                d=math.hypot(dx+rvx*t,dy+rvy*t)
                if tcpa is None: tcpa=t
                if dcpa is None: dcpa=d
            elif dcpa is None:
                dcpa=d2
    except Exception:
        pass
    return d2,rz,tcpa,dcpa


def relevant_actors(r, max_distance=45.0, max_abs_z=3.0):
    out=[]
    for a in (r.get("scenario_actors") or []):
        d2,rz,tcpa,dcpa=_actor_geometry(r,a)
        if d2 is None: continue
        if rz is not None and abs(float(rz)) > max_abs_z: continue
        if float(d2) <= max_distance:
            out.append((a,float(d2),rz,tcpa,dcpa))
    return out


def best_actor(r):
    """Prefer the most interaction-relevant actor, not simply nearest in 3-D."""
    acts=relevant_actors(r)
    if not acts: return None
    def key(x):
        _,d2,_,tcpa,dcpa=x
        # Future small-DCPA conflicts first, then current distance.
        future = tcpa is not None and float(tcpa) <= 8.0
        return (0 if future else 1, float(dcpa) if dcpa is not None else 1e9, d2)
    return min(acts,key=key)



def actor_speed(a):
    try:
        v=a.get("velocity") or [0,0,0]
        return math.sqrt(float(v[0])**2+float(v[1])**2+float(v[2])**2)
    except Exception:
        return 0.0


def find_first_visible_index(rows, max_distance=45.0):
    for i,r in enumerate(rows):
        if relevant_actors(r,max_distance=max_distance):
            return i
    return None


def find_motion_onset_index(rows, max_distance=45.0, speed_threshold=0.2):
    for i,r in enumerate(rows):
        for a,_,_,_,_ in relevant_actors(r,max_distance=max_distance):
            if actor_speed(a) > speed_threshold:
                return i
    return None


def find_event_index(rows, family, max_distance=45.0):
    """Find the response-alignment event for the configured intervention.

    * reaction-time sweeps: treatment is walker *motion timing*, so align to motion onset.
    * heading/direction sweeps: actor orientation/path intent already differs as soon as the
      pedestrian becomes visible, so align planner response to first visibility while also
      logging motion-onset DCPA/TCPA as the realized interaction dose.
    * other families: first on-plane interaction proximity (explicitly reported).
    """
    fam=str(family or '')
    if fam == 'pedestrian_reaction_time':
        i=find_motion_onset_index(rows,max_distance=max_distance)
        if i is not None:
            return i,'pedestrian_motion_onset'
    if fam in ('pedestrian_heading_sweep','pedestrian_direction_control'):
        i=find_first_visible_index(rows,max_distance=max_distance)
        if i is not None:
            return i,'pedestrian_first_visible_heading_exposure'
    i=find_first_visible_index(rows,max_distance=max_distance)
    if i is not None:
        return i,'first_onplane_actor_within_distance'
    return None,'not_found'

def trace_integrity(rows):
    if not rows: return False,"empty_trace"
    run_ids={str(r.get("run_id")) for r in rows if r.get("run_id") not in (None,"legacy")}
    pids={str(r.get("pid")) for r in rows if r.get("pid") is not None}
    if len(run_ids)>1: return False,"multiple_run_ids"
    if len(pids)>1: return False,"multiple_pids"
    prev_t=None; prev_s=None; resets=0
    for r in rows:
        try: t=float(r.get("timestamp"))
        except Exception: continue
        s=r.get("step")
        reset_here = prev_t is not None and t < prev_t - 1e-6
        if prev_s is not None and s is not None:
            try:
                reset_here = reset_here or int(s) < int(prev_s)
            except Exception:
                pass
        if reset_here:
            resets += 1
        prev_t=t; prev_s=s
    if resets: return False,f"timestamp_or_step_resets:{resets}"
    return True,""


def parse_log(trace_path):
    log=trace_path.with_name("stdout.log")
    if not log.exists():
        return {"route_evaluated":False,"route_completion_pct":None,"collision_count":None,"log_cleanup_error":False}
    txt=log.read_text(encoding="utf-8",errors="replace")
    clean=re.sub(r"\x1b\[[0-9;]*m","",txt)
    route_evaluated="Registering the route statistics" in clean
    rc=None; coll=None
    m=re.search(r"RouteCompletionTest\s*[│|]\s*(?:SUCCESS|FAILURE)\s*[│|]\s*([0-9.]+)\s*%",clean)
    if m: rc=float(m.group(1))
    m=re.search(r"CollisionTest\s*[│|]\s*(?:SUCCESS|FAILURE)\s*[│|]\s*([0-9.]+)\s*times",clean)
    if m: coll=float(m.group(1))
    return {"route_evaluated":route_evaluated,"route_completion_pct":rc,"collision_count":coll,
            "log_cleanup_error":"Failed to stop the agent" in clean}


def parse_scenario_meta(trace_path):
    p=trace_path.with_name("scenario_meta.json")
    if not p.exists(): return {}
    try: return json.load(open(p,encoding="utf-8"))
    except Exception: return {}


def _tta_to_point(row, xyz):
    try:
        ego=row.get("ego") or {}; loc=ego.get("location"); vel=ego.get("velocity")
        if not loc or not vel or not xyz: return None
        dx=float(xyz[0])-float(loc[0]); dy=float(xyz[1])-float(loc[1])
        dist=math.hypot(dx,dy)
        if dist < 1e-6: return 0.0
        ux,uy=dx/dist,dy/dist
        vproj=float(vel[0])*ux+float(vel[1])*uy
        return dist/vproj if vproj>0.05 else None
    except Exception: return None

def _intended_pedestrian_cpa(row, scenmeta, max_distance=45.0):
    """CPA at the first exposure using configured walker heading/speed.

    The walker may still be stationary in CARLA at first visibility. For heading-sweep
    interventions we need an exogenous dose measured before the policy can alter ego
    motion, so reconstruct the intended pedestrian velocity from scenario metadata.
    """
    walkers={}
    for w in (scenmeta.get("walker_actors") or []):
        try: walkers[int(w.get("actor_id"))]=w
        except Exception: pass
    ego=row.get("ego") or {}; el=ego.get("location"); ev=ego.get("velocity")
    if not walkers or not el or not ev: return None,None,None
    best=None
    for a,d2,rz,_,_ in relevant_actors(row,max_distance=max_distance):
        try: w=walkers.get(int(a.get("id")))
        except Exception: w=None
        if not w or w.get("world_yaw") is None or w.get("speed") is None: continue
        al=a.get("location") or [0,0,0]
        dx=float(al[0])-float(el[0]); dy=float(al[1])-float(el[1])
        yaw=math.radians(float(w["world_yaw"])); sp=float(w["speed"])
        avx,avy=sp*math.cos(yaw),sp*math.sin(yaw)
        rvx,rvy=avx-float(ev[0]),avy-float(ev[1])
        den=rvx*rvx+rvy*rvy
        if den > 1e-8:
            tcpa=max(0.0,-(dx*rvx+dy*rvy)/den)
            dcpa=math.hypot(dx+rvx*tcpa,dy+rvy*tcpa)
        else:
            tcpa=0.0; dcpa=math.hypot(dx,dy)
        cand=(float(dcpa),float(tcpa),int(a.get("id")),float(d2))
        if best is None or cand[0] < best[0]: best=cand
    if best is None: return None,None,None
    return best[1],best[0],best[2]


def parse_result(trace_path):
    p=trace_path.with_name("result.json")
    if not p.exists(): return {"checkpoint_finalized":False,"entry_status":"missing","n_result_records":0}
    try: obj=json.load(open(p,encoding="utf-8"))
    except Exception: return {"checkpoint_finalized":False,"entry_status":"invalid","n_result_records":0}
    cp=obj.get("_checkpoint") or {}
    rec=cp.get("records") or []
    glob=cp.get("global_record") or {}
    status=obj.get("entry_status")
    finalized=bool(rec or glob) and status != "Started"
    return {"checkpoint_finalized":finalized,"entry_status":status,"n_result_records":len(rec)}


def _seed_from_path(path):
    for part in path.parts:
        if part.startswith("seed_"):
            try: return int(part.split("_",1)[1])
            except Exception: return part
    return None


def _trapz_positive_reduction(samples, baseline):
    # samples: (t, desired_speed); integrate max(0, baseline-v(t)).
    if baseline is None or len(samples)<2: return None
    acc=0.0
    for (t0,v0),(t1,v1) in zip(samples,samples[1:]):
        y0=max(0.0,baseline-v0); y1=max(0.0,baseline-v1)
        acc += 0.5*(y0+y1)*(t1-t0)
    return acc


def summarize_trace(path, max_distance=45.0, pre_seconds=1.0, post_seconds=4.0):
    try: rows=load_trace(path)
    except Exception as exc:
        return {"trace":str(path),"trace_valid":False,"invalid_reason":str(exc),"route_evaluated":False}
    if not rows: return None
    valid,reason=trace_integrity(rows)
    logmeta=parse_log(path); resultmeta=parse_result(path)
    meta=rows[0].get("variant") or {}
    scenmeta=parse_scenario_meta(path)

    event_idx,event_definition=find_event_index(rows,meta.get("family"),max_distance=max_distance)
    if event_idx is None:
        event_idx=0
        event_found=False
    else:
        event_found=True
    event_t=float(rows[event_idx].get("timestamp",0.0))
    visible_idx=find_first_visible_index(rows,max_distance=max_distance)
    motion_idx=find_motion_onset_index(rows,max_distance=max_distance)
    visible_t=float(rows[visible_idx].get("timestamp",0.0)) if visible_idx is not None else None
    motion_t=float(rows[motion_idx].get("timestamp",0.0)) if motion_idx is not None else None
    collision_tta_at_visible=_tta_to_point(rows[visible_idx],scenmeta.get("collision_location")) if visible_idx is not None else None
    intended_tcpa_at_visible=intended_dcpa_at_visible=intended_actor_id=None
    if visible_idx is not None:
        intended_tcpa_at_visible,intended_dcpa_at_visible,intended_actor_id=_intended_pedestrian_cpa(
            rows[visible_idx],scenmeta,max_distance=max_distance)
    visible_ego=rows[visible_idx].get("ego") if visible_idx is not None else None
    event_ego=rows[event_idx].get("ego") or {}
    event_best=best_actor(rows[event_idx]) if event_found else None
    event_distance_2d=event_tcpa=event_dcpa=None
    if event_best:
        _,event_distance_2d,_,event_tcpa,event_dcpa=event_best
    motion_ego=rows[motion_idx].get("ego") if motion_idx is not None else None
    motion_best=best_actor(rows[motion_idx]) if motion_idx is not None else None
    motion_distance_2d=motion_tcpa=motion_dcpa=None
    if motion_best:
        _,motion_distance_2d,_,motion_tcpa,motion_dcpa=motion_best
    t0=event_t-pre_seconds; t1=event_t+post_seconds
    pre=[r for r in rows if t0 <= float(r.get("timestamp",0.0)) < event_t]
    post=[r for r in rows if event_t <= float(r.get("timestamp",0.0)) <= t1]
    active=post if post else rows[event_idx:]

    pre_ds=[desired_speed(r) for r in pre if desired_speed(r) is not None]
    post_pairs=[(float(r.get("timestamp",0.0)),desired_speed(r)) for r in active if desired_speed(r) is not None]
    post_ds=[v for _,v in post_pairs]
    baseline=median(pre_ds) if pre_ds else (post_ds[0] if post_ds else None)
    post_min=min(post_ds) if post_ds else None
    delta=(post_min-baseline) if (post_min is not None and baseline is not None) else None

    speeds=[]; d2s=[]; dcpa=[]; tcpa=[]; long_ttcs=[]; closings=[]
    for r in active:
        if r.get("ego") and r["ego"].get("speed") is not None: speeds.append(float(r["ego"]["speed"]))
        ba=best_actor(r)
        if ba:
            a,d2,rz,tca,dca=ba
            d2s.append(d2)
            if dca is not None: dcpa.append(float(dca))
            if tca is not None: tcpa.append(float(tca))
            if a.get("ttc_longitudinal") is not None: long_ttcs.append(float(a["ttc_longitudinal"]))
            if a.get("closing_speed") is not None: closings.append(float(a["closing_speed"]))

    brake_after=[float(r["timestamp"]) for r in active if float((r.get("control") or {}).get("brake",0.0)) > 0.5]
    brake_before=[float(r["timestamp"]) for r in pre if float((r.get("control") or {}).get("brake",0.0)) > 0.5]
    all_ds=[desired_speed(r) for r in rows if desired_speed(r) is not None]
    seed=rows[0].get("seed") or _seed_from_path(path)

    params=meta.get("params") or {}
    intervention_name=None; intervention_value=None
    for k in ("cra_reaction_time","cra_speed_perc","cra_ped_yaw_offset"):
        if k in params:
            intervention_name=k; intervention_value=params.get(k); break
    out={
        "trace":str(path),"agent":rows[0].get("agent"),"family":meta.get("family"),
        "route_id":meta.get("route_id"),"variant":meta.get("variant"),"risk_rank":meta.get("risk_rank"),"seed":seed,
        "intervention_name":intervention_name,"intervention_value":intervention_value,
        "run_id":rows[0].get("run_id"),"n_frames":len(rows),"trace_valid":valid,"invalid_reason":reason,
        **logmeta,**resultmeta,
        "event_found":event_found,"event_definition":event_definition,"first_visible_time":visible_t,
        "first_visible_ego_speed":(visible_ego or {}).get("speed") if visible_idx is not None else None,
        "intended_tcpa_at_first_visible":intended_tcpa_at_visible,
        "intended_dcpa_at_first_visible":intended_dcpa_at_visible,
        "intended_actor_id":intended_actor_id,
        "motion_onset_time":motion_t,
        "motion_delay_from_first_visible":((motion_t-visible_t) if (motion_t is not None and visible_t is not None) else None),
        "collision_tta_at_first_visible":collision_tta_at_visible,
        "configured_reaction_time":scenmeta.get("reaction_time"),
        "event_time":event_t if event_found else None,"n_event_window":len(active),
        "event_ego_speed":event_ego.get("speed") if event_found else None,
        "event_actor_distance_2d":event_distance_2d,
        "event_tcpa_2d":event_tcpa,
        "event_dcpa_2d":event_dcpa,
        "motion_onset_ego_speed":(motion_ego or {}).get("speed") if motion_idx is not None else None,
        "motion_onset_actor_distance_2d":motion_distance_2d,
        "motion_onset_tcpa_2d":motion_tcpa,
        "motion_onset_dcpa_2d":motion_dcpa,
        "pre_planner_desired_speed":baseline,
        "post_min_planner_desired_speed":post_min,
        "response_delta_speed":delta,
        "response_reduction_auc":_trapz_positive_reduction(post_pairs,baseline),
        "min_planner_desired_speed":min(all_ds) if all_ds else None,
        "mean_planner_desired_speed":mean(all_ds) if all_ds else None,
        "min_ego_speed_event_window":min(speeds) if speeds else None,
        "min_actor_distance_2d_event_window":min(d2s) if d2s else None,
        "min_dcpa_2d_event_window":min(dcpa) if dcpa else None,
        "min_tcpa_2d_event_window":min(tcpa) if tcpa else None,
        "min_longitudinal_ttc_event_window":min(long_ttcs) if long_ttcs else None,
        "max_closing_speed_event_window":max(closings) if closings else None,
        "preexisting_brake":bool(brake_before),
        "brake_latency_from_event":(min(brake_after)-event_t) if brake_after else None,
        "ever_braked_event_window":bool(brake_after),
    }
    # Scientific usability for response curves: trace must be internally coherent and
    # CARLA must have reached route criteria evaluation. Checkpoint finalization is
    # reported separately because an upstream cleanup bug can occur afterwards.
    out["usable_for_curve"]=bool(valid and logmeta["route_evaluated"] and event_found and post_ds)
    return out


def _bool(x): return str(x).lower() in ("1","true","yes")


def monotonic_violations(group, metric="post_min_planner_desired_speed", tol=0.25):
    # Higher risk rank should not yield a higher target/minimum desired speed.
    pts=[]
    for r in group:
        try:
            if r.get("risk_rank") is None or r.get(metric) is None: continue
            pts.append((int(r["risk_rank"]),float(r[metric])))
        except Exception: continue
    pts=sorted(pts)
    violations=[]
    for a,b in zip(pts,pts[1:]):
        if b[1] > a[1] + tol: violations.append((a,b))
    return violations


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--runs",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--max-distance",type=float,default=45.0)
    ap.add_argument("--pre-seconds",type=float,default=1.0)
    ap.add_argument("--post-seconds",type=float,default=4.0)
    args=ap.parse_args()
    traces=sorted(Path(args.runs).rglob("trace.jsonl"))
    summaries=[]
    for p in traces:
        s=summarize_trace(p,args.max_distance,args.pre_seconds,args.post_seconds)
        if s: summaries.append(s)
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    if not summaries:
        print("No traces found"); return
    fields=[]
    for s in summaries:
        for k in s:
            if k not in fields: fields.append(k)
    with open(out/"run_summary.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(summaries)

    groups={}
    for s in summaries:
        if not s.get("usable_for_curve") or s.get('family') == 'pedestrian_direction_control': continue
        groups.setdefault((s.get('agent'),s.get('family'),s.get('route_id'),s.get('seed')),[]).append(s)
    report=[]; complete_groups=0; bad=0
    for key,g in sorted(groups.items(),key=lambda kv:str(kv[0])):
        levels=len({x.get('risk_rank') for x in g if x.get('risk_rank') is not None})
        v=monotonic_violations(g)
        if levels>=3: complete_groups+=1
        if v: bad+=1
        report.append({"group":key,"n":len(g),"n_risk_levels":levels,"violations":v})
    with open(out/"monotonicity_report.json","w",encoding="utf-8") as f: json.dump(report,f,indent=2,ensure_ascii=False)
    invalid=sum(not bool(s.get("trace_valid")) for s in summaries)
    usable=sum(bool(s.get("usable_for_curve")) for s in summaries)
    print(f"traces={len(summaries)} invalid={invalid} usable_for_curve={usable} groups_with_>=3_levels={complete_groups} groups_with_nonmonotonicity={bad}")
    print(out/"run_summary.csv"); print(out/"monotonicity_report.json")
if __name__=="__main__": main()
