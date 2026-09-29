#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cradrive.xml_tools import list_scenarios


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--routes", required=True)
    p.add_argument("--scenario-type", default=None)
    args = p.parse_args()
    refs = list_scenarios(args.routes, args.scenario_type)
    for r in refs:
        print(json.dumps({
            "route_id": r.route_id,
            "town": r.town,
            "scenario_name": r.scenario_name,
            "scenario_type": r.scenario_type,
            "parameters": r.parameters,
        }, ensure_ascii=False))


if __name__ == "__main__":
    main()
