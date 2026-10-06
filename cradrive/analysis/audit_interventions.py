#!/usr/bin/env python3
"""Audit whether configured CRADrive intervention levels are physically separable.

This is a treatment-validity check, not a model-quality metric.  It is intended to
run before interpreting any risk->response curve.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def b(x):
    return str(x).lower() in ("1", "true", "yes")


def f(x):
    try:
        return float(x) if x not in (None, "") else None
    except Exception:
        return None


def spread(vals):
    vals=[x for x in vals if x is not None]
    return (max(vals)-min(vals)) if vals else None


def unique_rounded(vals, ndigits=1):
    return len({round(x, ndigits) for x in vals if x is not None})


def pairwise_monotone_fraction(points, higher_rank_should_lower_y=True, tol=0.25):
    """Fraction of rank-ordered pairs consistent with an expected monotone direction."""
    points=sorted((r,y) for r,y in points if r is not None and y is not None)
    good=total=0
    for i,(ra,ya) in enumerate(points):
        for rb,yb in points[i+1:]:
            total += 1
            if higher_rank_should_lower_y:
                good += (yb <= ya + tol)
            else:
                good += (yb >= ya - tol)
    return (good/total if total else None), total


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timing-tol", type=float, default=0.25,
                    help="seconds: matched timing spread tolerated for heading sweep")
    ap.add_argument("--ego-speed-tol", type=float, default=1.0,
                    help="m/s: pre/motion-onset ego-speed spread tolerated across matched levels")
    args=ap.parse_args()

    rows=list(csv.DictReader(open(args.summary, encoding="utf-8")))
    groups=defaultdict(list)
    for r in rows:
        fam=r.get("family") or ""
        if fam not in ("pedestrian_reaction_time", "pedestrian_heading_sweep", "pedestrian_direction_control"):
            continue
        if "trace_valid" in r and not b(r.get("trace_valid")):
            continue
        if "route_evaluated" in r and not b(r.get("route_evaluated")):
            continue
        groups[(r.get("agent"), fam, r.get("route_id"), r.get("seed"))].append(r)

    outrows=[]
    for (agent,fam,route,seed),g in sorted(groups.items(), key=lambda kv: str(kv[0])):
        # Exclude exact source nominal from intervention separability checks because it can
        # keep original Bench2Drive speed/idle randomness and has no intervention value.
        tx=[r for r in g if f(r.get("risk_rank")) is not None]
        levels=len({int(f(r.get("risk_rank"))) for r in tx if f(r.get("risk_rank")) is not None})
        vis=[f(r.get("first_visible_time")) for r in tx]
        mot=[f(r.get("motion_onset_time")) for r in tx]
        delay=[f(r.get("motion_delay_from_first_visible")) for r in tx]
        first_es=[f(r.get("first_visible_ego_speed")) for r in tx]
        motion_es=[f(r.get("motion_onset_ego_speed")) for r in tx]
        intended_dcpa=[f(r.get("intended_dcpa_at_first_visible")) for r in tx]
        motion_dcpa=[f(r.get("motion_onset_dcpa_2d")) for r in tx]
        configured=[f(r.get("configured_reaction_time")) for r in tx]
        tta_vis=[f(r.get("collision_tta_at_first_visible")) for r in tx]

        status="INSUFFICIENT"
        reasons=[]
        if levels >= 3:
            status="PASS"

        if fam == "pedestrian_reaction_time":
            # Larger reaction-time values should trigger earlier. If configured reaction
            # time is already >= ego TTA when walkers first appear, the condition is
            # immediately true and multiple levels may collapse to the same onset.
            saturated=0
            comparable=0
            for rt,tta in zip(configured,tta_vis):
                if rt is not None and tta is not None:
                    comparable += 1
                    saturated += (rt >= tta - 0.1)
            unique_motion=unique_rounded(mot,1)
            if levels >= 3 and unique_motion < max(3, levels-1):
                status="FAIL"
                reasons.append(f"motion_onset_collapse:{unique_motion}/{levels}_unique_0.1s")
            if comparable and saturated >= 2:
                status="FAIL"
                reasons.append(f"trigger_already_satisfied_at_first_visible:{saturated}/{comparable}")
            if spread(delay) is not None and spread(delay) < 0.2 and levels >= 3:
                status="FAIL"
                reasons.append("motion_delay_spread<0.2s")

        elif fam == "pedestrian_heading_sweep":
            # Heading is the treatment; first-visible/motion timing and ego state should
            # stay matched. Realized interaction geometry should vary after motion begins.
            if spread(vis) is not None and spread(vis) > args.timing_tol:
                status="FAIL"; reasons.append(f"first_visible_spread>{args.timing_tol}s")
            if spread(mot) is not None and spread(mot) > args.timing_tol:
                status="FAIL"; reasons.append(f"motion_onset_spread>{args.timing_tol}s")
            if spread(first_es) is not None and spread(first_es) > args.ego_speed_tol:
                status="FAIL"
                reasons.append(f"first_visible_ego_speed_spread>{args.ego_speed_tol}mps")
            if levels >= 3 and unique_rounded(intended_dcpa,1) < 3:
                status="FAIL"; reasons.append("intended_pre_response_DCPA_not_separable")
            pts=[(f(r.get("risk_rank")), f(r.get("intended_dcpa_at_first_visible"))) for r in tx]
            frac,npairs=pairwise_monotone_fraction(pts, higher_rank_should_lower_y=True, tol=0.25)
            if npairs and frac is not None and frac < 0.8:
                status="WARN" if status=="PASS" else status
                reasons.append(f"provisional_risk_rank_vs_intended_DCPA_consistency={frac:.2f}")

        elif fam == "pedestrian_direction_control":
            if spread(vis) is not None and spread(vis) > args.timing_tol:
                status="FAIL"; reasons.append(f"first_visible_spread>{args.timing_tol}s")
            if spread(mot) is not None and spread(mot) > args.timing_tol:
                status="FAIL"; reasons.append(f"motion_onset_spread>{args.timing_tol}s")

        outrows.append({
            "agent":agent,"family":fam,"route_id":route,"seed":seed,
            "n_intervention_levels":levels,"status":status,"reasons":";".join(reasons),
            "first_visible_spread_s":spread(vis),"motion_onset_spread_s":spread(mot),
            "motion_delay_spread_s":spread(delay),
            "first_visible_ego_speed_spread_mps":spread(first_es),
            "motion_onset_ego_speed_spread_mps":spread(motion_es),
            "intended_dcpa_first_visible_spread_m":spread(intended_dcpa),
            "motion_onset_dcpa_spread_m":spread(motion_dcpa),
            "unique_motion_onsets_0p1s":unique_rounded(mot,1),
            "unique_intended_dcpa_0p1m":unique_rounded(intended_dcpa,1),
            "unique_motion_dcpa_0p1m":unique_rounded(motion_dcpa,1),
        })

    out=Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    fields=["agent","family","route_id","seed","n_intervention_levels","status","reasons",
            "first_visible_spread_s","motion_onset_spread_s","motion_delay_spread_s",
            "first_visible_ego_speed_spread_mps","motion_onset_ego_speed_spread_mps",
            "intended_dcpa_first_visible_spread_m","motion_onset_dcpa_spread_m",
            "unique_motion_onsets_0p1s","unique_intended_dcpa_0p1m","unique_motion_dcpa_0p1m"]
    with open(out,"w",newline="",encoding="utf-8") as fh:
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(outrows)
    print(f"Wrote {len(outrows)} intervention-audit groups -> {out}")
    for r in outrows:
        print(f"{r['status']:12s} {r['agent']}/{r['family']}/route_{r['route_id']}/seed_{r['seed']} "
              f"levels={r['n_intervention_levels']} {r['reasons']}")


if __name__ == "__main__":
    main()
