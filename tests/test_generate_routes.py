import json, subprocess, sys, tempfile
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
b2d=Path('/mnt/data/cradrive_work/b2d/Bench2Drive-0.0.4')
if b2d.exists():
    with tempfile.TemporaryDirectory() as d:
        subprocess.check_call([sys.executable,str(repo/'tools/generate_routes.py'),'--b2d-root',str(b2d),'--out',d])
        manifest=Path(d)/'manifest.jsonl'
        rows=[json.loads(x) for x in open(manifest)]
        assert len(rows)==34
        subprocess.check_call([sys.executable,str(repo/'tools/check_matched.py'),str(manifest)])
