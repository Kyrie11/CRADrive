#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def indent(elem, level=0):
    i = "\n" + level * "   "
    if len(elem):
        if not elem.text or not elem.text.strip(): elem.text = i + "   "
        for child in elem:
            indent(child, level + 1)
        if not elem[-1].tail or not elem[-1].tail.strip(): elem[-1].tail = i
    if level and (not elem.tail or not elem.tail.strip()): elem.tail = i


def find_route(root, route_id, source_type):
    for route in root.iter("route"):
        if route.attrib.get("id") != str(route_id):
            continue
        scens = [s for s in route.find("scenarios").iter("scenario") if s.attrib.get("type") == source_type]
        if len(scens) != 1:
            raise RuntimeError(f"route {route_id}: expected exactly one {source_type}, got {len(scens)}")
        return route, scens[0]
    raise KeyError(f"route {route_id} with scenario {source_type} not found")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b2d-root", required=True)
    ap.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "configs/pilot_v1.json"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.load(open(args.config, "r", encoding="utf-8"))
    source = Path(args.b2d_root) / cfg["source_routes"]
    root = ET.parse(source).getroot()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []

    for fam in cfg["families"]:
        for route_id in fam["route_ids"]:
            route, source_scen = find_route(root, route_id, fam["source_type"])
            for variant in fam["variants"]:
                route_copy = copy.deepcopy(route)
                target_scen = None
                for s in route_copy.find("scenarios").iter("scenario"):
                    if s.attrib.get("type") == fam["source_type"]:
                        target_scen = s
                        break
                assert target_scen is not None
                use_source = bool(variant.get("use_source_scenario", False))
                if not use_source:
                    target_scen.attrib["type"] = fam["target_type"]
                    target_scen.attrib["name"] = f"{fam['target_type']}_{variant['label']}"
                    # Remove stale CRADrive params in case source XML was already modified.
                    for child in list(target_scen):
                        if child.tag.startswith("cra_"):
                            target_scen.remove(child)
                    for key, value in variant.get("params", {}).items():
                        ET.SubElement(target_scen, key, {"value": str(value)})

                xml_root = ET.Element("routes")
                xml_root.append(route_copy)
                indent(xml_root)
                run_dir = out / fam["name"] / f"route_{route_id}" / variant["label"]
                run_dir.mkdir(parents=True, exist_ok=True)
                xml_path = run_dir / "route.xml"
                ET.ElementTree(xml_root).write(xml_path, encoding="utf-8", xml_declaration=True)

                meta = {
                    "family": fam["name"], "source_type": fam["source_type"],
                    "target_type": fam["source_type"] if use_source else fam["target_type"], "route_id": str(route_id),
                    "variant": variant["label"], "risk_rank": variant.get("risk_rank"),
                    "risk_order": fam["risk_order"], "params": variant.get("params", {}),
                    "use_source_scenario": use_source,
                    "notes": fam.get("notes", ""), "route_xml": str(xml_path.resolve())
                }
                meta_path = run_dir / "variant.json"
                json.dump(meta, open(meta_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                meta["variant_json"] = str(meta_path.resolve())
                manifest.append(meta)

    manifest_path = out / "manifest.jsonl"
    with open(manifest_path, "w", encoding="utf-8") as f:
        for row in manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Generated {len(manifest)} matched route variants -> {out}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
