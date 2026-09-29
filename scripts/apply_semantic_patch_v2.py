#!/usr/bin/env python3
from __future__ import annotations
import argparse, shutil
from pathlib import Path

def replace_once(text, old, new, label):
    if new in text: return text, False
    if old not in text: raise RuntimeError(f'Could not find expected source for {label}')
    return text.replace(old,new,1), True

def patch(root: Path):
    sr=root/'scenario_runner'/'srunner'/'scenarios'
    if not sr.exists(): raise RuntimeError(f'No scenario_runner/srunner/scenarios under {root}')
    changed=[]
    f=sr/'object_crash_vehicle.py'; s=f.read_text()
    pairs=[
      ("self._adversary_speed = 2.0  # Speed of the adversary [m/s]", "self._adversary_speed = get_value_parameter(config, 'adversary_speed', float, 2.0)  # CRADrive"),
      ("self._reaction_time = 2.1  # Time the agent has to react to avoid the collision [s]", "self._reaction_time = get_value_parameter(config, 'reaction_time', float, 2.1)  # CRADrive"),
      ("self._min_trigger_dist = 6.0  # Min distance to the collision location that triggers the adversary [m]", "self._min_trigger_dist = get_value_parameter(config, 'min_trigger_dist', float, 6.0)  # CRADrive"),
      ("self._reaction_time = 2.15", "self._reaction_time = get_value_parameter(config, 'reaction_time', float, 2.15)  # CRADrive")]
    anyc=False
    for old,new in pairs:
        # duplicates adversary/min trigger across classes: replace all occurrences safely
        if new in s: continue
        if old in s:
            s=s.replace(old,new); anyc=True
    if anyc:
        b=f.with_suffix(f.suffix+'.cradrive.bak');
        if not b.exists(): shutil.copy2(f,b)
        f.write_text(s); changed.append(str(f))
    f=sr/'parking_cut_in.py'; s=f.read_text(); anyc=False
    helper="""\n\ndef _cradrive_param(config, name, default):\n    try:\n        return float(config.other_parameters[name]['value'])\n    except Exception:\n        return float(default)\n"""
    if '_cradrive_param' not in s:
        anchor='from srunner.tools.background_manager import LeaveSpaceInFront, ChangeRoadBehavior\n'
        if anchor not in s: raise RuntimeError('parking_cut_in import anchor changed')
        s=s.replace(anchor,anchor+helper,1); anyc=True
    for old,new in [
      ("self._adversary_speed = 13.0  # Speed of the adversary [m/s]", "self._adversary_speed = _cradrive_param(config, 'adversary_speed', 13.0)  # CRADrive"),
      ("self._reaction_time = 2.35  # Time the agent has to react to avoid the collision [s]", "self._reaction_time = _cradrive_param(config, 'reaction_time', 2.35)  # CRADrive"),
      ("self._min_trigger_dist = 10.0  # Min distance to the collision location that triggers the adversary [m]", "self._min_trigger_dist = _cradrive_param(config, 'min_trigger_dist', 10.0)  # CRADrive")]:
        if new not in s and old in s: s=s.replace(old,new,1); anyc=True
    if anyc:
        b=f.with_suffix(f.suffix+'.cradrive.bak');
        if not b.exists(): shutil.copy2(f,b)
        f.write_text(s); changed.append(str(f))
    print('patched' if changed else 'already patched', root)
    for x in changed: print(' ',x)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--bench2drive',action='append',required=True); args=ap.parse_args()
    for r in args.bench2drive: patch(Path(r).resolve())
if __name__=='__main__': main()
