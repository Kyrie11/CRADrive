#!/usr/bin/env python3
"""Fast integrity report for CRADrive result directories."""
import argparse,csv
from pathlib import Path
from cradrive.analysis.summarize import summarize_trace

ap=argparse.ArgumentParser(); ap.add_argument('--runs',required=True); args=ap.parse_args()
rows=[]
for p in sorted(Path(args.runs).rglob('trace.jsonl')):
    s=summarize_trace(p)
    if s: rows.append(s)
print('trace_valid route_eval checkpoint usable agent family route variant seed reason')
for s in rows:
    print(int(bool(s.get('trace_valid'))),int(bool(s.get('route_evaluated'))),int(bool(s.get('checkpoint_finalized'))),
          int(bool(s.get('usable_for_curve'))),s.get('agent'),s.get('family'),s.get('route_id'),s.get('variant'),s.get('seed'),s.get('invalid_reason') or '-')
