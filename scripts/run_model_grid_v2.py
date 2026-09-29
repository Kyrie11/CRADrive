#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def pypath(env, paths): env['PYTHONPATH']=os.pathsep.join([str(Path(x).resolve()) for x in paths if x]+([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--model',choices=['dt','lead','simlingo'],required=True); ap.add_argument('--manifest',required=True); ap.add_argument('--out',required=True); ap.add_argument('--carla',required=True); ap.add_argument('--root',required=True); ap.add_argument('--checkpoint',required=True); ap.add_argument('--bench2drive'); ap.add_argument('--dt-config'); ap.add_argument('--gpu',type=int,default=0); ap.add_argument('--seeds',default='0'); ap.add_argument('--only',default=''); ap.add_argument('--max-runs',type=int,default=0); ap.add_argument('--overwrite',action='store_true'); ap.add_argument('--timeout',type=float,default=600); args=ap.parse_args()
 root=Path(args.root).resolve(); carla=Path(args.carla).resolve(); seeds=[int(x) for x in args.seeds.split(',') if x.strip()]; man=json.loads(Path(args.manifest).read_text()); conds=man['conditions'];
 if args.only: conds=[c for c in conds if args.only in c['condition_id']]
 if args.max_runs: conds=conds[:args.max_runs]
 if args.model=='dt':
  if not args.bench2drive or not args.dt_config: raise SystemExit('--bench2drive and --dt-config required for dt')
  b2d=Path(args.bench2drive).resolve(); alias=b2d/'DriveTransformer';
  if not alias.exists(): alias.symlink_to(root,target_is_directory=True)
  evaluator=b2d/'leaderboard/leaderboard/leaderboard_evaluator.py'; agent=ROOT/'team_code/drivetransformer_cradrive_agent.py'; base_paths=[ROOT,b2d,b2d/'leaderboard',b2d/'scenario_runner',root]
 elif args.model=='lead':
  b2d=root/'3rd_party/Bench2Drive'; evaluator=b2d/'leaderboard/leaderboard/leaderboard_evaluator.py'; agent=ROOT/'team_code/lead_cradrive_agent.py'; base_paths=[root,ROOT,b2d/'leaderboard',b2d/'scenario_runner']
 else:
  b2d=root/'Bench2Drive'; evaluator=b2d/'leaderboard/leaderboard/leaderboard_evaluator.py'; agent=ROOT/'team_code/simlingo_cradrive_agent.py'; base_paths=[root,ROOT,b2d/'leaderboard',b2d/'scenario_runner']
 out=Path(args.out).resolve(); out.mkdir(parents=True,exist_ok=True); run_count=0
 for seed in seeds:
  for c in conds:
   run_count+=1; rd=out/f"seed_{seed}"/c['condition_id']; done=rd/'DONE'
   if done.exists() and not args.overwrite: continue
   if rd.exists() and args.overwrite: shutil.rmtree(rd)
   rd.mkdir(parents=True,exist_ok=True); (rd/'condition.json').write_text(json.dumps(c,indent=2))
   env=os.environ.copy(); env.update({'CARLA_ROOT':str(carla),'CRADRIVE_CONDITION_ID':c['condition_id'],'CRADRIVE_TRACE_PATH':str(rd/'trace.jsonl'),'CUDA_VISIBLE_DEVICES':str(args.gpu),'ROUTES':str(Path(c['xml']).resolve()),'SAVE_PATH':str(rd)+'/'})
   if args.model=='lead': env.update({'IS_BENCH2DRIVE':'1','PLANNER_TYPE':'only_traj','CHECKPOINT_DIR':str(Path(args.checkpoint).resolve()),'PYTHONUNBUFFERED':'1'})
   paths=base_paths+[carla/'PythonAPI',carla/'PythonAPI/carla']; dist=carla/'PythonAPI/carla/dist'; paths += list(dist.glob('carla-*.egg')) if dist.exists() else []; pypath(env,paths)
   if args.model=='dt': agent_cfg=f"{Path(args.dt_config).resolve()}+{Path(args.checkpoint).resolve()}+{c['condition_id']}"
   else: agent_cfg=str(Path(args.checkpoint).resolve())
   cmd=[sys.executable,str(evaluator),f"--routes={Path(c['xml']).resolve()}",'--repetitions=1','--track=SENSORS',f"--checkpoint={rd/'checkpoint.json'}",f"--agent={agent}",f"--agent-config={agent_cfg}",'--debug=0',f"--port={30000+seed*100}",f"--traffic-manager-port={50000+seed*100}",f"--traffic-manager-seed={seed}",f"--timeout={args.timeout}"]
   if args.model=='dt': cmd.append(f'--gpu-rank={args.gpu}')
   print(f"[{args.model}] seed={seed} {c['condition_id']}")
   with (rd/'stdout.log').open('w') as f: proc=subprocess.run(cmd,cwd=str(root if args.model!='dt' else b2d),env=env,stdout=f,stderr=subprocess.STDOUT)
   (rd/'returncode.txt').write_text(str(proc.returncode));
   if proc.returncode==0: done.write_text('ok\n')
   else: print('FAILED, see',rd/'stdout.log')
   time.sleep(3)
 print('attempted',run_count,'runs')
if __name__=='__main__': main()
