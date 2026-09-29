from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def read_jsonl(path: Path) -> List[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _dynamic_actor(row: dict) -> Optional[dict]:
    actors = row.get("scenario_actors") or []
    # Pedestrian-crossing pilots may also contain a parked blocker vehicle. Prefer
    # walkers whenever present so the response metric follows the actual adversary.
    walkers = [a for a in actors if str(a.get("type_id", "")).startswith("walker.")]
    if walkers:
        walkers.sort(key=lambda a: float(a.get("distance_m", 1e9)))
        return walkers[0]

    vehicles = [a for a in actors if str(a.get("type_id", "")).startswith("vehicle.")]
    if not vehicles:
        return None
    def speed(a):
        v = a.get("velocity") or [0.0, 0.0, 0.0]
        try:
            return math.sqrt(sum(float(x) ** 2 for x in v[:3]))
        except Exception:
            return 0.0
    moving = [a for a in vehicles if speed(a) > 0.2]
    candidates = moving or vehicles
    candidates.sort(key=lambda a: float(a.get("distance_m", 1e9)))
    return candidates[0]


def _first_matching(rows: Sequence[dict], pred) -> Optional[dict]:
    for row in rows:
        if pred(row):
            return row
    return None


def summarize_trace(rows: Sequence[dict]) -> Dict[str, object]:
    if not rows:
        return {
            "trace_frames": 0,
            "hazard_frames": 0,
            "min_speed_near_hazard_mps": None,
            "max_brake_near_hazard": None,
            "min_dynamic_actor_distance_m": None,
            "brake_onset_actor_distance_m": None,
            "speed_at_20m_mps": None,
            "speed_at_15m_mps": None,
            "speed_at_10m_mps": None,
            "speed_at_5m_mps": None,
        }

    actor_pairs: List[Tuple[dict, dict]] = []
    for r in rows:
        a = _dynamic_actor(r)
        if a is not None:
            actor_pairs.append((r, a))

    min_actor_distance = None
    if actor_pairs:
        min_actor_distance = min(float(a.get("distance_m", 1e9)) for _, a in actor_pairs)

    # Localize behavioral metrics around the target actor. Whole-route minimum
    # speed is misleading because DriveTransformer intentionally brakes during
    # its first initialization frames and routes can contain unrelated stops.
    hazard_pairs = [
        (r, a) for r, a in actor_pairs
        if float(a.get("distance_m", 1e9)) <= 40.0
        and float(a.get("longitudinal_m", 0.0)) >= -5.0
    ]
    hazard_speeds = [float(r.get("speed_mps", 0.0)) for r, _ in hazard_pairs if r.get("speed_mps") is not None]
    hazard_brakes = [float((r.get("control") or {}).get("brake", 0.0)) for r, _ in hazard_pairs]

    brake_onset_distance = None
    for r, a in actor_pairs:
        control = r.get("control") or {}
        if (float(control.get("brake", 0.0)) >= 0.15
                and float(a.get("distance_m", 1e9)) <= 50.0
                and float(a.get("longitudinal_m", 0.0)) >= -5.0):
            brake_onset_distance = float(a.get("distance_m"))
            break

    first_actor = actor_pairs[0] if actor_pairs else None
    out: Dict[str, object] = {
        "trace_frames": len(rows),
        "hazard_frames": len(hazard_pairs),
        "min_speed_near_hazard_mps": min(hazard_speeds) if hazard_speeds else None,
        "max_brake_near_hazard": max(hazard_brakes) if hazard_brakes else None,
        "min_dynamic_actor_distance_m": min_actor_distance,
        "brake_onset_actor_distance_m": brake_onset_distance,
        "first_actor_distance_m": float(first_actor[1].get("distance_m")) if first_actor else None,
        "speed_at_first_actor_mps": float(first_actor[0].get("speed_mps")) if first_actor and first_actor[0].get("speed_mps") is not None else None,
    }

    for threshold in (20, 15, 10, 5):
        candidate = None
        best_gap = 1e9
        for r, a in actor_pairs:
            d = float(a.get("distance_m", 1e9))
            gap = abs(d - threshold)
            if gap < best_gap:
                best_gap = gap
                candidate = r
        out[f"speed_at_{threshold}m_mps"] = (
            float(candidate.get("speed_mps")) if candidate is not None and best_gap <= 3.0 else None
        )

    # Predicted trajectory response: forward displacement of the final fixed-time waypoint.
    endpoints = []
    for r in rows:
        traj = r.get("model_prediction") or {}
        pts = traj.get("ego_traj_fix_time")
        if pts:
            try:
                x, y = pts[-1][0], pts[-1][1]
                endpoints.append(math.hypot(float(x), float(y)))
            except Exception:
                pass
    out["mean_predicted_horizon_displacement_m"] = (
        sum(endpoints) / len(endpoints) if endpoints else None
    )
    return out


def load_checkpoint_summary(path: Path) -> Dict[str, object]:
    if not path.exists() or path.stat().st_size == 0:
        return {"checkpoint_found": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"checkpoint_found": False, "checkpoint_parse_error": True}

    records = ((data.get("_checkpoint") or {}).get("records") or [])
    if not records:
        return {"checkpoint_found": True, "route_record_found": False}
    record = records[0]
    scores = record.get("scores") or {}
    infractions = record.get("infractions") or {}
    collision_keys = [k for k in infractions if "collision" in k.lower()]
    collision_count = sum(len(infractions.get(k) or []) for k in collision_keys)
    return {
        "checkpoint_found": True,
        "route_record_found": True,
        "status": record.get("status"),
        "driving_score": scores.get("score_composed"),
        "route_completion": scores.get("score_route"),
        "infraction_penalty": scores.get("score_penalty"),
        "collision_count": collision_count,
        "num_infractions": record.get("num_infractions"),
    }


def _rank(values: Sequence[float]) -> List[float]:
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i + 1
        while j < len(indexed) and indexed[j][1] == indexed[i][1]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = avg
        i = j
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    rx, ry = _rank(xs), _rank(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    deny = math.sqrt(sum((b - my) ** 2 for b in ry))
    if denx == 0 or deny == 0:
        return None
    return num / (denx * deny)

def summarize_physics(rows: Sequence[dict]) -> Dict[str, object]:
    vals={'min_ttc_collision_radius_s':[], 'min_dcpa_m':[], 'max_required_stop_decel_mps2':[], 'max_realized_decel_mps2':[]}
    for r in rows:
        a=_dynamic_actor(r)
        if a is None: continue
        if a.get('ttc_collision_radius_s') is not None: vals['min_ttc_collision_radius_s'].append(float(a['ttc_collision_radius_s']))
        if a.get('dcpa_m') is not None: vals['min_dcpa_m'].append(float(a['dcpa_m']))
        if a.get('required_stop_decel_mps2') is not None and float(a.get('longitudinal_m',-1))>0: vals['max_required_stop_decel_mps2'].append(float(a['required_stop_decel_mps2']))
        if r.get('longitudinal_accel_mps2') is not None: vals['max_realized_decel_mps2'].append(max(0.0,-float(r['longitudinal_accel_mps2'])))
    return {
      'min_ttc_collision_radius_s': min(vals['min_ttc_collision_radius_s']) if vals['min_ttc_collision_radius_s'] else None,
      'min_dcpa_m': min(vals['min_dcpa_m']) if vals['min_dcpa_m'] else None,
      'max_required_stop_decel_mps2': max(vals['max_required_stop_decel_mps2']) if vals['max_required_stop_decel_mps2'] else None,
      'max_realized_decel_mps2': max(vals['max_realized_decel_mps2']) if vals['max_realized_decel_mps2'] else None,
    }

def pairwise_direction_accuracy(risks: Sequence[float], responses: Sequence[float], higher_response_for_higher_risk=True, eps=1e-6):
    good=tot=0
    for i in range(len(risks)):
      for j in range(i+1,len(risks)):
        dr=risks[i]-risks[j]; dy=responses[i]-responses[j]
        if abs(dr)<=eps: continue
        tot+=1; good += int((dr*dy>0) if higher_response_for_higher_risk else (dr*dy<0))
    return good/tot if tot else None

def activation_physics(rows: Sequence[dict]) -> Dict[str, object]:
    """Risk at adversary activation, before much closed-loop reaction can accumulate.
    Walkers are dormant below ground before activation, so their first visible frame is activation.
    For vehicle cut-ins, use the first frame where the selected scenario vehicle is moving.
    """
    for r in rows:
        a=_dynamic_actor(r)
        if a is None: continue
        tid=str(a.get('type_id',''))
        v=a.get('velocity') or [0,0,0]
        sp=math.sqrt(sum(float(x)**2 for x in v[:3]))
        active=tid.startswith('walker.') or sp>0.2
        if not active: continue
        return {
          'activation_ttc_collision_radius_s': a.get('ttc_collision_radius_s'),
          'activation_dcpa_m': a.get('dcpa_m'),
          'activation_required_stop_decel_mps2': a.get('required_stop_decel_mps2'),
          'activation_actor_distance_m': a.get('distance_m'),
          'activation_actor_longitudinal_m': a.get('longitudinal_m'),
          'activation_ego_speed_mps': r.get('speed_mps'),
        }
    return {'activation_ttc_collision_radius_s':None,'activation_dcpa_m':None,'activation_required_stop_decel_mps2':None,
            'activation_actor_distance_m':None,'activation_actor_longitudinal_m':None,'activation_ego_speed_mps':None}
