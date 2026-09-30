#!/usr/bin/env python3
import argparse, os, sys
from pathlib import Path

ap=argparse.ArgumentParser(); ap.add_argument('--expect-b2d', required=True); args=ap.parse_args()
import leaderboard
import srunner
print('leaderboard:', Path(leaderboard.__file__).resolve())
print('srunner:', Path(srunner.__file__).resolve())
expect=Path(args.expect_b2d).resolve()
for mod in (Path(leaderboard.__file__).resolve(), Path(srunner.__file__).resolve()):
    if expect not in mod.parents:
        raise SystemExit(f'ERROR: imported benchmark code outside Bench2Drive 0.0.4: {mod}')
print('OK: imports resolve to requested Bench2Drive root')
