#!/usr/bin/env python3
"""Verify route variants are identical except scenario type/name and cra_* tags."""
import argparse, json, hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


def canonical(path):
    root = ET.parse(path).getroot()
    for s in root.iter("scenario"):
        if s.attrib.get("type", "").startswith("CRA"):
            # Restore semantic base type from our custom type names.
            mapping = {"CRAPedestrianCrossing":"PedestrianCrossing", "CRAHighwayCutIn":"HighwayCutIn", "CRAHardBreakRoute":"HardBreakRoute"}
            s.attrib["type"] = mapping.get(s.attrib["type"], s.attrib["type"])
            s.attrib["name"] = "NORMALIZED"
        for c in list(s):
            if c.tag.startswith("cra_"):
                s.remove(c)
    return ET.tostring(root, encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("manifest"); args=ap.parse_args()
    rows=[json.loads(x) for x in open(args.manifest, encoding="utf-8") if x.strip()]
    groups={}
    for r in rows: groups.setdefault((r["family"],r["route_id"]),[]).append(r)
    bad=0
    for key, rs in groups.items():
        hashes={hashlib.sha256(canonical(r["route_xml"])).hexdigest() for r in rs}
        ok=len(hashes)==1
        print(("OK  " if ok else "FAIL"), key, f"n={len(rs)}")
        bad += 0 if ok else 1
    raise SystemExit(1 if bad else 0)
if __name__=="__main__": main()
