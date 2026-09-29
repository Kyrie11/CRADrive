#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def check(label, path, kind="exists"):
    p = Path(path).expanduser().resolve()
    ok = p.exists()
    print(f"[{'OK' if ok else 'MISSING'}] {label}: {p}")
    return ok


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bench2drive", required=True)
    p.add_argument("--drivetransformer", required=True)
    p.add_argument("--carla", required=True)
    p.add_argument("--config", required=True)
    p.add_argument("--checkpoint", required=True)
    args = p.parse_args()

    b2d = Path(args.bench2drive).resolve()
    dt = Path(args.drivetransformer).resolve()
    carla = Path(args.carla).resolve()
    checks = [
        check("Bench2Drive evaluator", b2d / "leaderboard/leaderboard/leaderboard_evaluator.py"),
        check("Bench2Drive scenario runner", b2d / "scenario_runner/srunner/scenarios/object_crash_vehicle.py"),
        check("DriveTransformer agent", dt / "team_code/drivetransformer_b2d_agent.py"),
        check("DriveTransformer config", args.config),
        check("DriveTransformer checkpoint", args.checkpoint),
        check("CARLA server", carla / "CarlaUE4.sh"),
        check("CARLA PythonAPI", carla / "PythonAPI"),
    ]
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    if not all(checks):
        raise SystemExit(2)
    print("Setup paths look valid. Dependency/import validation happens in the active DriveTransformer conda env during run_grid.py.")


if __name__ == "__main__":
    main()
