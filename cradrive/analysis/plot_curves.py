#!/usr/bin/env python3
import argparse, csv
from pathlib import Path
import matplotlib.pyplot as plt

ap=argparse.ArgumentParser(); ap.add_argument('--summary',required=True); ap.add_argument('--out',required=True); args=ap.parse_args()
rows=list(csv.DictReader(open(args.summary,encoding='utf-8')))
out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
groups={}
for r in rows:
    if r['family'] in ('', 'pedestrian_direction_control'): continue
    if not r['min_planner_desired_speed']: continue
    groups.setdefault((r['agent'],r['family'],r['route_id']),[]).append(r)
for (agent,fam,route),g in groups.items():
    # Average repetitions/seeds by risk rank.
    by={}
    for r in g: by.setdefault(int(r['risk_rank']),[]).append(float(r['min_planner_desired_speed']))
    xs=sorted(by); ys=[sum(by[x])/len(by[x]) for x in xs]
    plt.figure()
    plt.plot(xs,ys,marker='o')
    plt.xlabel('Intervention risk rank (higher = intended higher risk)')
    plt.ylabel('Minimum planner desired speed (m/s)')
    plt.title(f'{agent} | {fam} | route {route}')
    plt.grid(True,alpha=0.3)
    plt.tight_layout(); plt.savefig(out/f'{agent}__{fam}__route_{route}.png',dpi=160); plt.close()
print(f'Wrote {len(groups)} figures to {out}')
