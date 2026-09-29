#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

EXPECTED_SHA256 = "c6168ffd0402bafc71375424aa755c3278f20c8544ef7fc50b315fec472e17f2"
MARKER = "# CRADRIVE_SEMANTIC_PARAMS_V1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def patch_text(text: str) -> str:
    if MARKER in text:
        return text

    old_dynamic = """        self._adversary_speed = 2.0  # Speed of the adversary [m/s]\n        self._crossing_angle = get_value_parameter(config, 'crossing_angle', float, 0)\n        self._reaction_time = 2.1  # Time the agent has to react to avoid the collision [s]\n        self._reaction_time += 0.1 * floor(self._crossing_angle / 5)\n        self._min_trigger_dist = 6.0  # Min distance to the collision location that triggers the adversary [m]\n"""
    new_dynamic = """        # CRADRIVE_SEMANTIC_PARAMS_V1\n        self._adversary_speed = get_value_parameter(config, 'adversary_speed', float, 2.0)\n        self._crossing_angle = get_value_parameter(config, 'crossing_angle', float, 0)\n        _default_reaction_time = 2.1 + 0.1 * floor(self._crossing_angle / 5)\n        self._reaction_time = get_value_parameter(config, 'reaction_time', float, _default_reaction_time)\n        self._min_trigger_dist = get_value_parameter(config, 'min_trigger_dist', float, 6.0)\n"""

    old_parking = """        self._adversary_speed = 2.0  # Speed of the adversary [m/s]\n        self._min_trigger_dist = 6.0  # Min distance to the collision location that triggers the adversary [m]\n        self._ego_end_distance = 40\n"""
    new_parking = """        self._adversary_speed = get_value_parameter(config, 'adversary_speed', float, 2.0)\n        self._min_trigger_dist = get_value_parameter(config, 'min_trigger_dist', float, 6.0)\n        self._ego_end_distance = 40\n"""

    old_reaction = """        # Time the agent has to react to avoid the collision [s]\n        self._reaction_time = 2.15\n        self._reaction_time += 0.1 * floor(self._crossing_angle / 5)\n"""
    new_reaction = """        # Time the agent has to react to avoid the collision [s].\n        _default_reaction_time = 2.15 + 0.1 * floor(self._crossing_angle / 5)\n        self._reaction_time = get_value_parameter(config, 'reaction_time', float, _default_reaction_time)\n"""

    for old, new, label in [
        (old_dynamic, new_dynamic, "DynamicObjectCrossing"),
        (old_parking, new_parking, "ParkingCrossingPedestrian speed/trigger"),
        (old_reaction, new_reaction, "ParkingCrossingPedestrian reaction"),
    ]:
        if old not in text:
            raise RuntimeError(f"Could not locate expected {label} block. Refusing a partial patch.")
        text = text.replace(old, new, 1)
    return text


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bench2drive", required=True)
    p.add_argument("--revert", action="store_true")
    p.add_argument("--force-version", action="store_true", help="Allow patching when source SHA differs from uploaded 0.0.4")
    args = p.parse_args()

    target = Path(args.bench2drive).resolve() / "scenario_runner/srunner/scenarios/object_crash_vehicle.py"
    backup = target.with_suffix(target.suffix + ".cradrive.bak")
    if not target.exists():
        raise SystemExit(f"Missing {target}")

    if args.revert:
        if not backup.exists():
            raise SystemExit(f"No backup found at {backup}")
        shutil.copy2(backup, target)
        print(f"Restored {target} from {backup}")
        return

    original = target.read_text(encoding="utf-8")
    if MARKER in original:
        print("Patch already applied; nothing to do.")
        return

    digest = sha256(target)
    if digest != EXPECTED_SHA256 and not args.force_version:
        raise SystemExit(
            f"Unexpected source hash {digest}. Expected {EXPECTED_SHA256}.\n"
            "This script was generated against the uploaded Bench2Drive 0.0.4 source. "
            "Use --force-version only after reviewing the diff."
        )

    if not backup.exists():
        shutil.copy2(target, backup)
    patched = patch_text(original)
    target.write_text(patched, encoding="utf-8")
    print(f"Patched: {target}")
    print(f"Backup:  {backup}")


if __name__ == "__main__":
    main()
