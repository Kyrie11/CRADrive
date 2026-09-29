#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from cradrive.xml_tools import find_scenario,set_scenario_parameter,set_weather,write_tree,write_json

def slug(x): return re.sub(r'[^A-Za-z0-9_]+','_',str(x).replace('-','m').replace('.','p'))
def index_routes(route_dir):
    out=[]
    for p in sorted(Path(route_dir).glob('*.xml')):
        try: tree=ET.parse(p)
        except Exception: continue
        for route in tree.getroot().findall('route'):
            scs=route.find('scenarios')
            if scs is None: continue
            for sc in scs.findall('scenario'):
                out.append((sc.get('type',''),sc.get('name',''),route.get('id',''),route.get('town',''),p))
    return out

def single_route_tree(src, route_id):
    tree=ET.parse(src); root=tree.getroot(); matches=[r for r in root.findall('route') if r.get('id')==str(route_id)]
    if len(matches)!=1: raise RuntimeError(f'{src}: route {route_id} count={len(matches)}')
    nr=ET.Element(root.tag,root.attrib); nr.append(matches[0]); return ET.ElementTree(nr),matches[0]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--route-dir',required=True); ap.add_argument('--config',default=str(ROOT/'configs/pilot_v2.json')); ap.add_argument('--out',required=True); ap.add_argument('--routes-per-scenario',type=int,default=0); args=ap.parse_args()
    cfg=json.loads(Path(args.config).read_text()); idx=index_routes(args.route_dir); out=Path(args.out).resolve(); (out/'routes').mkdir(parents=True,exist_ok=True)
    manifest={'canonical_route_dir':str(Path(args.route_dir).resolve()),'conditions':[]}
    n=args.routes_per_scenario or cfg.get('routes_per_scenario',3)
    for exp in cfg['experiments']:
        cands=[x for x in idx if x[0]==exp['scenario_type']][:n]
        if len(cands)<n: raise RuntimeError(f"Only {len(cands)} routes for {exp['scenario_type']}")
        for _,scname,rid,town,src in cands:
            for v in exp['values']:
                tree,route=single_route_tree(src,rid); sc=find_scenario(route,exp['scenario_type'],scname); set_scenario_parameter(sc,exp['parameter'],v)
                cid=f"{exp['name']}__route_{rid}__{exp['parameter']}_{slug(v)}"; xp=out/'routes'/f'{cid}.xml'; write_tree(tree,xp)
                manifest['conditions'].append({'condition_id':cid,'experiment':exp['name'],'kind':'causal','route_id':rid,'town':town,'scenario_type':exp['scenario_type'],'scenario_name':scname,'variable':exp['parameter'],'value':v,'risk_order':exp['risk_order'],'xml':str(xp)})
            base=exp['values'][len(exp['values'])//2]
            for wc in cfg.get('appearance_controls',[]):
                tree,route=single_route_tree(src,rid); sc=find_scenario(route,exp['scenario_type'],scname); set_scenario_parameter(sc,exp['parameter'],base); set_weather(route,wc['attrs'])
                cid=f"{exp['name']}__route_{rid}__appearance_{slug(wc['name'])}"; xp=out/'routes'/f'{cid}.xml'; write_tree(tree,xp)
                manifest['conditions'].append({'condition_id':cid,'experiment':exp['name'],'kind':'appearance_control','route_id':rid,'town':town,'scenario_type':exp['scenario_type'],'scenario_name':scname,'variable':'appearance','value':wc['name'],'baseline_causal_value':base,'xml':str(xp)})
    write_json(manifest,out/'manifest.json'); print(f"Generated {len(manifest['conditions'])} conditions across {len(set(x['route_id'] for x in manifest['conditions']))} routes")
if __name__=='__main__': main()
