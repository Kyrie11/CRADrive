#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cradrive.xml_tools import (
    clone_single_route_tree,
    find_scenario,
    get_weather_dict,
    set_scenario_parameter,
    set_weather,
    write_json,
    write_tree,
)


def slug(x: object) -> str:
    s = str(x).replace("-", "m").replace(".", "p")
    return re.sub(r"[^A-Za-z0-9_]+", "_", s)


def main():
    p = argparse.ArgumentParser(description="Generate single-route paired intervention XML files for CRADrive.")
    p.add_argument("--routes", required=True, help="Bench2Drive source routes XML")
    p.add_argument("--config", default=str(ROOT / "configs" / "pilot.json"))
    p.add_argument("--out", required=True)
    p.add_argument("--only", default="", help="Optional experiment name to generate")
    p.add_argument("--no-weather-controls", action="store_true")
    args = p.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_root = Path(args.out).resolve()
    routes_dir = out_root / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source_routes": str(Path(args.routes).resolve()),
        "config": str(Path(args.config).resolve()),
        "conditions": [],
    }

    for exp in config["experiments"]:
        if args.only and exp["name"] != args.only:
            continue
        for value in exp["values"]:
            tree, route = clone_single_route_tree(args.routes, str(exp["route_id"]))
            scenario = find_scenario(route, exp["scenario_type"], exp.get("scenario_name"))
            before = None
            for child in list(scenario):
                if child.tag == exp["parameter"]:
                    before = child.get("value")
                    break
            set_scenario_parameter(scenario, exp["parameter"], value)
            cid = f"{exp['name']}__{exp['parameter']}_{slug(value)}"
            xml_path = routes_dir / f"{cid}.xml"
            write_tree(tree, xml_path)
            manifest["conditions"].append({
                "condition_id": cid,
                "experiment": exp["name"],
                "kind": "causal",
                "route_id": str(exp["route_id"]),
                "scenario_type": exp["scenario_type"],
                "scenario_name": exp.get("scenario_name"),
                "variable": exp["parameter"],
                "value": value,
                "original_value": before,
                "xml": str(xml_path),
                "weather": get_weather_dict(route),
            })

        if not args.no_weather_controls:
            # Weather is a negative-control intervention: geometry and scenario timing remain unchanged.
            baseline_value = exp["values"][len(exp["values"]) // 2]
            for weather in config.get("weather_controls", []):
                tree, route = clone_single_route_tree(args.routes, str(exp["route_id"]))
                scenario = find_scenario(route, exp["scenario_type"], exp.get("scenario_name"))
                set_scenario_parameter(scenario, exp["parameter"], baseline_value)
                set_weather(route, weather["attrs"])
                cid = f"{exp['name']}__weather_{slug(weather['name'])}"
                xml_path = routes_dir / f"{cid}.xml"
                write_tree(tree, xml_path)
                manifest["conditions"].append({
                    "condition_id": cid,
                    "experiment": exp["name"],
                    "kind": "nuisance_weather",
                    "route_id": str(exp["route_id"]),
                    "scenario_type": exp["scenario_type"],
                    "scenario_name": exp.get("scenario_name"),
                    "variable": "weather",
                    "value": weather["name"],
                    "baseline_causal_value": baseline_value,
                    "weather_attrs": weather["attrs"],
                    "xml": str(xml_path),
                })

    write_json(manifest, out_root / "manifest.json")
    print(f"Generated {len(manifest['conditions'])} conditions")
    print(out_root / "manifest.json")


if __name__ == "__main__":
    main()
