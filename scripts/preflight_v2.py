#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, sys
from pathlib import Path

def ck(label,p,kind='exists'):
    p=Path(p).expanduser().resolve(); ok=p.exists() and (kind!='file' or p.is_file()) and (kind!='dir' or p.is_dir())
    print(f"[{'OK' if ok else 'FAIL'}] {label}: {p}"); return ok

def main():
    a=argparse.ArgumentParser();
    for x in ['carla','bench2drive','dt-root','dt-config','dt-checkpoint','lead-root','lead-checkpoint','simlingo-root','simlingo-checkpoint']: a.add_argument('--'+x,required=True)
    q=a.parse_args(); ok=True
    ok &= ck('CARLA server',Path(q.carla)/'CarlaUE4.sh','file')
    ok &= ck('external B2D evaluator',Path(q.bench2drive)/'leaderboard/leaderboard/leaderboard_evaluator.py','file')
    ok &= ck('DriveTransformer agent',Path(q.dt_root)/'team_code/drivetransformer_b2d_agent.py','file'); ok &= ck('DT config',q.dt_config,'file'); ok &= ck('DT checkpoint',q.dt_checkpoint,'file')
    ok &= ck('LEAD agent',Path(q.lead_root)/'lead/inference/sensor_agent.py','file'); ok &= ck('LEAD B2D evaluator',Path(q.lead_root)/'3rd_party/Bench2Drive/leaderboard/leaderboard/leaderboard_evaluator.py','file'); ok &= ck('LEAD checkpoint dir',q.lead_checkpoint,'dir')
    ok &= ck('LEAD canonical routes',Path(q.lead_root)/'data/benchmark_routes/bench2drive','dir')
    ok &= ck('SimLingo agent',Path(q.simlingo_root)/'team_code/agent_simlingo.py','file'); ok &= ck('SimLingo B2D evaluator',Path(q.simlingo_root)/'Bench2Drive/leaderboard/leaderboard/leaderboard_evaluator.py','file'); ok &= ck('SimLingo checkpoint',q.simlingo_checkpoint,'file')
    if not ok: raise SystemExit(2)
if __name__=='__main__': main()
