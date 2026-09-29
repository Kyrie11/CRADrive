from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class ScenarioRef:
    route_id: str
    town: str
    scenario_name: str
    scenario_type: str
    parameters: Dict[str, str]


def _scenario_params(scenario: ET.Element) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for child in list(scenario):
        if child.tag in {"trigger_point", "other_actor"}:
            continue
        if "value" in child.attrib:
            out[child.tag] = child.attrib["value"]
    return out


def list_scenarios(xml_path: str | Path, scenario_type: Optional[str] = None) -> List[ScenarioRef]:
    tree = ET.parse(str(xml_path))
    refs: List[ScenarioRef] = []
    for route in tree.getroot().findall("route"):
        scenarios = route.find("scenarios")
        if scenarios is None:
            continue
        for scenario in scenarios.findall("scenario"):
            stype = scenario.get("type", "")
            if scenario_type and stype != scenario_type:
                continue
            refs.append(
                ScenarioRef(
                    route_id=route.get("id", ""),
                    town=route.get("town", ""),
                    scenario_name=scenario.get("name", ""),
                    scenario_type=stype,
                    parameters=_scenario_params(scenario),
                )
            )
    return refs


def find_route(root: ET.Element, route_id: str) -> ET.Element:
    for route in root.findall("route"):
        if route.get("id") == str(route_id):
            return route
    raise KeyError(f"Route id {route_id!r} was not found")


def find_scenario(route: ET.Element, scenario_type: str, scenario_name: Optional[str] = None) -> ET.Element:
    scenarios = route.find("scenarios")
    if scenarios is None:
        raise KeyError(f"Route {route.get('id')} has no <scenarios>")
    matches = []
    for scenario in scenarios.findall("scenario"):
        if scenario.get("type") != scenario_type:
            continue
        if scenario_name is not None and scenario.get("name") != scenario_name:
            continue
        matches.append(scenario)
    if not matches:
        raise KeyError(
            f"No scenario type={scenario_type!r}, name={scenario_name!r} "
            f"in route {route.get('id')}"
        )
    if len(matches) > 1 and scenario_name is None:
        raise ValueError(
            f"Route {route.get('id')} has {len(matches)} scenarios of type {scenario_type}; "
            "pass scenario_name explicitly"
        )
    return matches[0]


def set_scenario_parameter(scenario: ET.Element, name: str, value: object) -> None:
    for child in list(scenario):
        if child.tag == name:
            child.set("value", str(value))
            return
    child = ET.Element(name)
    child.set("value", str(value))
    # Put custom parameters before trigger_point for readability only.
    insert_at = len(list(scenario))
    for i, existing in enumerate(list(scenario)):
        if existing.tag == "trigger_point":
            insert_at = i
            break
    scenario.insert(insert_at, child)


def get_weather_dict(route: ET.Element) -> List[Dict[str, str]]:
    node = route.find("weathers")
    if node is None:
        return []
    return [dict(w.attrib) for w in node.findall("weather")]


def set_weather(route: ET.Element, attrs: Dict[str, object]) -> None:
    node = route.find("weathers")
    if node is None:
        node = ET.Element("weathers")
        route.insert(0, node)
        for pct in (0, 100):
            w = ET.SubElement(node, "weather")
            w.set("route_percentage", str(pct))
    for weather in node.findall("weather"):
        for key, value in attrs.items():
            weather.set(key, str(value))


def clone_single_route_tree(source_xml: str | Path, route_id: str) -> Tuple[ET.ElementTree, ET.Element]:
    source = ET.parse(str(source_xml))
    route = find_route(source.getroot(), str(route_id))
    new_root = ET.Element(source.getroot().tag, source.getroot().attrib)
    cloned = copy.deepcopy(route)
    new_root.append(cloned)
    return ET.ElementTree(new_root), cloned


def indent_xml(tree: ET.ElementTree) -> None:
    try:
        ET.indent(tree, space="   ")  # Python >= 3.9
    except AttributeError:
        pass


def write_tree(tree: ET.ElementTree, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    indent_xml(tree)
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


def write_json(obj: object, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
