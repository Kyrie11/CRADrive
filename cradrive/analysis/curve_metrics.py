#!/usr/bin/env python3
"""Compute descriptive dose-response curve diagnostics from run_summary.csv.

These are pilot diagnostics, not a substitute for a physics/expert oracle.
"""
import argparse,csv,json,math,statistics
from pathlib import Path


def b(x): return str(x).lower() in ('1','true','yes')
def f(x):
    try: return float(x) if x not in (None,'') else None
    except Exception: return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--summary',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--metric',default='post_min_planner_desired_speed')
    ap.add_argument('--tolerance',type=float,default=0.25)
    args=ap.parse_args()
    rows=list(csv.DictReader(open(args.summary,encoding='utf-8')))
    groups={}
    for r in rows:
        if r.get('family') in ('',None,'pedestrian_direction_control'): continue
        if 'usable_for_curve' in r and not b(r.get('usable_for_curve')): continue
        y=f(r.get(args.metric)); rr=f(r.get('risk_rank'))
        if y is None or rr is None: continue
        groups.setdefault((r.get('agent'),r.get('family'),r.get('route_id')),[]).append(r)
    outrows=[]
    for key,g in sorted(groups.items(),key=lambda kv:str(kv[0])):
        by={}
        for r in g:
            rank=int(float(r['risk_rank'])); by.setdefault(rank,[]).append(float(r[args.metric]))
        ranks=sorted(by); means={k:statistics.mean(by[k]) for k in ranks}
        pairs=0; violations=0
        for i,a in enumerate(ranks):
            for bb in ranks[i+1:]:
                pairs+=1
                # Expected: larger risk rank -> same/lower desired speed.
                if means[bb] > means[a] + args.tolerance: violations+=1
        adjacent=sum(means[b_] > means[a] + args.tolerance for a,b_ in zip(ranks,ranks[1:]))
        span=(means[ranks[0]]-means[ranks[-1]]) if len(ranks)>=2 else None
        outrows.append({
            'agent':key[0],'family':key[1],'route_id':key[2],
            'metric':args.metric,'n_risk_levels':len(ranks),
            'min_repeats_per_level':min((len(by[k]) for k in ranks),default=0),
            'pairwise_monotonic_violation_rate':violations/pairs if pairs else None,
            'adjacent_violation_count':adjacent,
            'low_to_high_risk_response_span_mps':span,
            'means_by_risk_rank':json.dumps(means,sort_keys=True),
        })
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    fields=['agent','family','route_id','metric','n_risk_levels','min_repeats_per_level','pairwise_monotonic_violation_rate','adjacent_violation_count','low_to_high_risk_response_span_mps','means_by_risk_rank']
    with open(out,'w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(outrows)
    print(f'Wrote {len(outrows)} curve groups -> {out}')
if __name__=='__main__': main()
