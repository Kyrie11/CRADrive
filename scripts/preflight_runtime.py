#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def prepend(path):
    path = str(Path(path).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)


def main():
    p = argparse.ArgumentParser(description="Validate imports in the active DriveTransformer conda environment.")
    p.add_argument("--bench2drive", required=True)
    p.add_argument("--drivetransformer", required=True)
    p.add_argument("--carla", required=True)
    args = p.parse_args()

    b2d = Path(args.bench2drive).resolve()
    dt = Path(args.drivetransformer).resolve()
    carla_root = Path(args.carla).resolve()

    alias = b2d / "DriveTransformer"
    if not alias.exists():
        alias.symlink_to(dt, target_is_directory=True)
        print(f"[OK] created {alias} -> {dt}")

    prepend(b2d)
    prepend(b2d / "leaderboard")
    prepend(b2d / "leaderboard/team_code")
    prepend(b2d / "scenario_runner")
    prepend(dt)
    prepend(carla_root / "PythonAPI")
    prepend(carla_root / "PythonAPI/carla")
    dist = carla_root / "PythonAPI/carla/dist"
    for egg in sorted(dist.glob("carla-*.egg")) if dist.exists() else []:
        prepend(egg)

    checks = []
    for name in ["carla", "torch", "mmcv", "py_trees", "leaderboard", "srunner"]:
        try:
            module = __import__(name)
            version = getattr(module, "__version__", "n/a")
            print(f"[OK] import {name} version={version}")
            checks.append(True)
        except Exception as exc:
            print(f"[FAIL] import {name}: {exc!r}")
            checks.append(False)

    try:
        from DriveTransformer.team_code.drivetransformer_b2d_agent import DriveTransformerAgent
        print(f"[OK] DriveTransformer agent import: {DriveTransformerAgent.__name__}")
        checks.append(True)
    except Exception as exc:
        print(f"[FAIL] DriveTransformer agent import: {exc!r}")
        checks.append(False)

    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version}")
    if not all(checks):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
