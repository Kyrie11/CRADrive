#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def add_path(env, key, value):
    old = env.get(key, "")
    env[key] = str(value) + (os.pathsep + old if old else "")


def build_env(args, condition, run_dir):
    env = os.environ.copy()
    b2d = Path(args.bench2drive).resolve()
    dt = Path(args.drivetransformer).resolve()
    carla = Path(args.carla).resolve()

    env["CARLA_ROOT"] = str(carla)
    env["IS_BENCH2DRIVE"] = "True"
    env["CRADRIVE_CONDITION_ID"] = condition["condition_id"]
    env["CRADRIVE_TRACE_PATH"] = str(run_dir / "trace.jsonl")
    env["CRADRIVE_OUTPUT_ROOT"] = str(Path(args.out).resolve())
    env["CRADRIVE_SAVE_IMAGES_EVERY"] = str(args.save_images_every)

    # Make both upstream repos importable without installing CRADrive into the conda env.
    add_path(env, "PYTHONPATH", ROOT)
    add_path(env, "PYTHONPATH", b2d)
    add_path(env, "PYTHONPATH", b2d / "leaderboard")
    add_path(env, "PYTHONPATH", b2d / "leaderboard/team_code")
    add_path(env, "PYTHONPATH", b2d / "scenario_runner")
    add_path(env, "PYTHONPATH", dt)
    add_path(env, "PYTHONPATH", carla / "PythonAPI")
    add_path(env, "PYTHONPATH", carla / "PythonAPI/carla")
    dist = carla / "PythonAPI/carla/dist"
    if dist.exists():
        for egg in sorted(dist.glob("carla-*.egg")):
            add_path(env, "PYTHONPATH", egg)
    return env


def ensure_dt_alias(b2d: Path, dt: Path):
    alias = b2d / "DriveTransformer"
    if alias.exists() or alias.is_symlink():
        try:
            if alias.resolve() == dt.resolve():
                return
        except Exception:
            pass
        raise RuntimeError(
            f"{alias} already exists and does not resolve to {dt}. "
            "DriveTransformer's official agent imports through the name 'DriveTransformer'."
        )
    alias.symlink_to(dt, target_is_directory=True)
    print(f"Created symlink: {alias} -> {dt}")


def main():
    p = argparse.ArgumentParser(description="Run CRADrive conditions sequentially with the DriveTransformer Bench2Drive agent.")
    p.add_argument("--manifest", required=True)
    p.add_argument("--bench2drive", required=True)
    p.add_argument("--drivetransformer", required=True)
    p.add_argument("--carla", required=True)
    p.add_argument("--dt-config", required=True)
    p.add_argument("--dt-checkpoint", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument("--base-port", type=int, default=30000)
    p.add_argument("--base-tm-port", type=int, default=50000)
    p.add_argument("--traffic-manager-seed", type=int, default=0)
    p.add_argument("--timeout", type=float, default=600.0)
    p.add_argument("--sleep-between", type=float, default=5.0)
    p.add_argument("--save-images-every", type=int, default=0, help="Save front/BEV JPEG every N ticks; 0 disables")
    p.add_argument("--only", default="", help="Substring filter on condition_id")
    p.add_argument("--experiment", default="", help="Exact experiment-name filter")
    p.add_argument("--kind", choices=["causal", "nuisance_weather"], default="")
    p.add_argument("--max-runs", type=int, default=0)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    b2d = Path(args.bench2drive).resolve()
    dt = Path(args.drivetransformer).resolve()
    ensure_dt_alias(b2d, dt)

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    conditions = manifest["conditions"]
    if args.only:
        conditions = [c for c in conditions if args.only in c["condition_id"]]
    if args.experiment:
        conditions = [c for c in conditions if c.get("experiment") == args.experiment]
    if args.kind:
        conditions = [c for c in conditions if c.get("kind") == args.kind]
    if args.max_runs > 0:
        conditions = conditions[: args.max_runs]

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    agent = ROOT / "team_code/drivetransformer_cradrive_agent.py"
    evaluator = b2d / "leaderboard/leaderboard/leaderboard_evaluator.py"

    print(f"Will run {len(conditions)} condition(s) sequentially")
    for idx, cond in enumerate(conditions):
        run_dir = out_root / cond["condition_id"]
        checkpoint = run_dir / "checkpoint.json"
        live = run_dir / "live_results.txt"
        stdout = run_dir / "stdout.log"
        done = run_dir / "DONE"
        if done.exists() and not args.overwrite:
            print(f"[{idx+1}/{len(conditions)}] skip completed {cond['condition_id']}")
            continue
        if args.overwrite and run_dir.exists():
            shutil.rmtree(run_dir)
        elif run_dir.exists() and not done.exists():
            # A previous attempt was incomplete. Avoid appending to stale JSONL or
            # asking leaderboard to interpret a partial checkpoint as a fresh run.
            for stale in ["trace.jsonl", "checkpoint.json", "live_results.txt", "stdout.log", "returncode.txt"]:
                try:
                    (run_dir / stale).unlink()
                except FileNotFoundError:
                    pass
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "condition.json").write_text(json.dumps(cond, indent=2), encoding="utf-8")

        env = build_env(args, cond, run_dir)
        team_config = f"{Path(args.dt_config).resolve()}+{Path(args.dt_checkpoint).resolve()}+{cond['condition_id']}"
        cmd = [
            sys.executable,
            str(evaluator),
            f"--routes={Path(cond['xml']).resolve()}",
            "--repetitions=1",
            "--track=SENSORS",
            f"--checkpoint={checkpoint}",
            f"--debug-checkpoint={live}",
            f"--agent={agent}",
            f"--agent-config={team_config}",
            "--debug=0",
            f"--port={args.base_port}",
            f"--traffic-manager-port={args.base_tm_port}",
            f"--traffic-manager-seed={args.traffic_manager_seed}",
            f"--timeout={args.timeout}",
            f"--gpu-rank={args.gpu}",
        ]
        print(f"[{idx+1}/{len(conditions)}] {cond['condition_id']}")
        print(" ".join(cmd))
        if args.dry_run:
            continue
        with stdout.open("w", encoding="utf-8") as f:
            proc = subprocess.run(cmd, cwd=str(b2d), env=env, stdout=f, stderr=subprocess.STDOUT)
        (run_dir / "returncode.txt").write_text(str(proc.returncode) + "\n", encoding="utf-8")
        if proc.returncode == 0:
            done.write_text("ok\n", encoding="utf-8")
        else:
            print(f"  WARNING: return code {proc.returncode}; inspect {stdout}")
        if idx + 1 < len(conditions):
            time.sleep(args.sleep_between)


if __name__ == "__main__":
    main()
