#!/usr/bin/env python3
"""Plot only scientifically usable CRADrive response curves by default."""
import argparse
import csv
import math
import statistics
import sys
from pathlib import Path
import matplotlib.pyplot as plt


def as_bool(x): return str(x).lower() in ("1","true","yes")

def as_float(x):
    try: return float(x) if x not in (None,"") else None
    except Exception: return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--summary',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--metric',default='post_min_planner_desired_speed')
    ap.add_argument('--min-levels',type=int,default=3)
    ap.add_argument('--allow-incomplete',action='store_true',help='plot singleton/incomplete diagnostic data')
    argv=sys.argv[1:]
    # Defensive compatibility: the reported user error shows plot_curves.py was
    # passed twice (once as Python's script and once as argv[1]). Drop only an
    # exact duplicate of this file; other unknown arguments still fail loudly.
    if argv:
        try:
            if Path(argv[0]).resolve() == Path(__file__).resolve():
                print(f'WARN: dropping duplicated script argument: {argv[0]}', file=sys.stderr)
                argv=argv[1:]
        except Exception:
            pass
    args=ap.parse_args(argv)
    rows=list(csv.DictReader(open(args.summary,encoding='utf-8')))
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    groups={}
    for r in rows:
        if r.get('family') in ('',None,'pedestrian_direction_control'): continue
        if not args.allow_incomplete and 'usable_for_curve' in r and not as_bool(r.get('usable_for_curve')): continue
        if as_float(r.get(args.metric)) is None: continue
        groups.setdefault((r.get('agent'),r.get('family'),r.get('route_id')),[]).append(r)
    written=0; skipped=0
    for (agent,fam,route),g in sorted(groups.items(),key=lambda kv:str(kv[0])):
        by={}
        for r in g:
            try: rank=int(float(r['risk_rank']))
            except Exception: continue
            by.setdefault(rank,[]).append(float(r[args.metric]))
        xs=sorted(by)
        if len(xs)<args.min_levels and not args.allow_incomplete:
            print(f"SKIP {agent}/{fam}/route_{route}: only {len(xs)} risk level(s), need {args.min_levels}",file=sys.stderr)
            skipped+=1; continue
        if not xs: continue
        ys=[statistics.mean(by[x]) for x in xs]
        yerr=[statistics.stdev(by[x]) if len(by[x])>1 else 0.0 for x in xs]
        plt.figure()
        plt.errorbar(xs,ys,yerr=yerr,marker='o',capsize=3)
        plt.xlabel('Intervention risk rank (higher = intended higher risk)')
        plt.ylabel(args.metric.replace('_',' '))
        plt.title(f'{agent} | {fam} | route {route}')
        plt.grid(True,alpha=0.3)
        plt.tight_layout(); plt.savefig(out/f'{agent}__{fam}__route_{route}__{args.metric}.png',dpi=160); plt.close()
        written+=1
    print(f'Wrote {written} figures to {out}; skipped_incomplete={skipped}')

if __name__=='__main__': main()
