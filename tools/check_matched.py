#!/usr/bin/env python3
"""Verify route variants are identical except the intended CRADrive scenario parameters."""
import argparse, json, hashlib
import xml.etree.ElementTree as ET

MAPPING={"CRAPedestrianCrossing":"PedestrianCrossing", "CRAHighwayCutIn":"HighwayCutIn", "CRAHardBreakRoute":"HardBreakRoute", "CRAHardBreak":"HardBreakRoute"}


def canonical(path, source_type):
    root=ET.parse(path).getroot()
    for s in root.iter("scenario"):
        mapped=MAPPING.get(s.attrib.get("type",""),s.attrib.get("type",""))
        if mapped == source_type:
            s.attrib["type"]=source_type
            # Scenario name is not a treatment variable. Normalize both exact B2D
            # nominal controls and CRADrive custom variants.
            s.attrib["name"]="NORMALIZED"
            for c in list(s):
                if c.tag.startswith("cra_"):
                    s.remove(c)
    # Ignore serialization-only whitespace left after removing treatment tags.
    for e in root.iter():
        if e.text is not None and not e.text.strip(): e.text = None
        if e.tail is not None and not e.tail.strip(): e.tail = None
    return ET.tostring(root,encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("manifest"); args=ap.parse_args()
    rows=[json.loads(x) for x in open(args.manifest,encoding="utf-8") if x.strip()]
    groups={}
    for r in rows: groups.setdefault((r["family"],r["route_id"]),[]).append(r)
    bad=0
    for key,rs in groups.items():
        hashes={hashlib.sha256(canonical(r["route_xml"],r["source_type"])).hexdigest() for r in rs}
        ok=len(hashes)==1
        print(("OK  " if ok else "FAIL"),key,f"n={len(rs)}")
        bad += 0 if ok else 1
    raise SystemExit(1 if bad else 0)
if __name__=="__main__": main()
