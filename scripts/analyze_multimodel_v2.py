#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,sys
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from cradrive.metrics import read_jsonl,summarize_trace,summarize_physics,activation_physics,load_checkpoint_summary,pairwise_direction_accuracy,spearman

def sf(x):
 try:return float(x)
 except:return None
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--manifest',required=True); ap.add_argument('--model-run',action='append',required=True,help='name=/path/to/runs'); ap.add_argument('--out',required=True); args=ap.parse_args()
 man=json.loads(Path(args.manifest).read_text()); models={x.split('=',1)[0]:Path(x.split('=',1)[1]) for x in args.model_run}; rows=[]
 for m,root in models.items():
  for seed_dir in sorted(root.glob('seed_*')):
   seed=seed_dir.name.split('_',1)[1]
   for c in man['conditions']:
    rd=seed_dir/c['condition_id']; tr=read_jsonl(rd/'trace.jsonl'); row={'model':m,'seed':seed,**c,**summarize_trace(tr),**summarize_physics(tr),**activation_physics(tr),**load_checkpoint_summary(rd/'checkpoint.json')}; rows.append(row)
 out=Path(args.out); out.mkdir(parents=True,exist_ok=True); fields=[]
 for r in rows:
  for k,v in r.items():
   if k not in fields and not isinstance(v,(dict,list)): fields.append(k)
 with (out/'summary.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows({k:r.get(k) for k in fields} for r in rows)
 rep=['# CRADrive v0.2 hypothesis report\n\n','Primary question: do strong driving agents change behavior in the physically correct direction as matched semantic risk changes, while remaining comparatively invariant to risk-preserving appearance changes? H0 first validates that the intervention ordering changes activation-time physical risk.\n\n']
 groups=defaultdict(list)
 for r in rows:
  if r.get('kind')=='causal': groups[(r['model'],r['seed'],r['experiment'],r['route_id'])].append(r)
 rep.append('## H0 intervention validity / H1 causal-direction response\n')
 model_cda=defaultdict(list)
 for key,g in sorted(groups.items()):
  g=[x for x in g if sf(x.get('value')) is not None];
  if len(g)<3: continue
  # reaction_time: smaller value means higher intervention urgency. H0 checks that this
  # actually changes activation-time physical risk before using it as the causal ordering.
  urg=[-sf(x['value']) for x in g]; brakes=[sf(x.get('max_brake_near_hazard')) for x in g]; speeds=[sf(x.get('speed_at_10m_mps')) for x in g]
  act_req=[sf(x.get('activation_required_stop_decel_mps2')) for x in g]; act_ttc=[sf(x.get('activation_ttc_collision_radius_s')) for x in g]
  h0_req=spearman(urg,act_req) if all(x is not None for x in act_req) else None; h0_ttc=spearman(urg,act_ttc) if all(x is not None for x in act_ttc) else None
  cda_b=pairwise_direction_accuracy(urg,brakes,True) if all(x is not None for x in brakes) else None; cda_s=pairwise_direction_accuracy(urg,speeds,False) if all(x is not None for x in speeds) else None
  model_cda[key[0]].extend([x for x in [cda_b,cda_s] if x is not None]); rep.append(f"- {key}: H0 rho(urgency, activation required decel)={h0_req}, rho(urgency, activation TTC)={h0_ttc}; CDA(brake)={cda_b}, CDA(speed@10m)={cda_s}\n")
 rep.append('\n## Cross-model decision gate\n')
 for m,vals in model_cda.items(): rep.append(f"- {m}: mean causal-direction accuracy={sum(vals)/len(vals):.3f} over {len(vals)} route/metric tests\n")
 rep.append('\n### Pre-registered interpretation\n- **GO**: at least 2/3 model families show repeated CDA < 0.8 or clear non-monotonic curves on >=2 scenario/route groups, while standard driving score remains relatively stable or fails to expose the difference.\n- **STRONG GO**: the above is accompanied by cross-model disagreement (similar Driving Score but >0.20 CDA gap), and causal interventions produce larger response changes than appearance controls.\n- **NO-GO / reformulate**: all three models are consistently monotonic (CDA >=0.9), appearance controls are stable, and causal diagnostics strongly track ordinary score.\n- Do not claim CRA magnitude alignment yet unless an expert policy/reference response is added; v0.2 establishes direction/threshold correctness against a privileged physics oracle.\n')
 (out/'hypothesis_report.md').write_text(''.join(rep))
 print(out/'summary.csv'); print(out/'hypothesis_report.md')
if __name__=='__main__': main()
