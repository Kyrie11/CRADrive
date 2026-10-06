"""Model-agnostic online logging for CRADrive.

The probe deliberately does not feed privileged simulator state back into the policy.
It only logs it for post-hoc causal-response analysis.
"""
import json
import math
import os
from pathlib import Path


def _vec(v):
    return [float(v.x), float(v.y), float(v.z)]


def _finite(x):
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _jsonable(x):
    try:
        import numpy as np
        if isinstance(x, np.ndarray):
            return x.tolist()
        if isinstance(x, np.generic):
            return x.item()
    except Exception:
        pass
    try:
        import torch
        if torch.is_tensor(x):
            return x.detach().float().cpu().tolist()
    except Exception:
        pass
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    return str(x)


def _cpa_2d(dx, dy, rvx, rvy):
    """Constant-velocity 2-D time/distance to closest point of approach.

    Relative velocity is actor - ego. tcpa is clipped at zero because a closest
    approach in the past should not be interpreted as future collision risk.
    """
    denom = rvx * rvx + rvy * rvy
    if denom <= 1e-8:
        return None, math.hypot(dx, dy)
    tcpa = -(dx * rvx + dy * rvy) / denom
    tcpa = max(0.0, tcpa)
    cx = dx + rvx * tcpa
    cy = dy + rvy * tcpa
    return tcpa, math.hypot(cx, cy)


class CRAProbeMixin:
    """Append one compact JSON record per policy step."""

    def _cra_init(self, agent_name):
        self._cra_agent_name = agent_name
        self._cra_run_id = os.environ.get("CRADRIVE_RUN_ID", "legacy")
        self._cra_seed = os.environ.get("CRADRIVE_SEED")
        self._cra_pid = os.getpid()
        trace_path = os.environ.get("CRADRIVE_TRACE_PATH")
        if not trace_path:
            trace_dir = Path(os.environ.get("CRADRIVE_TRACE_DIR", "."))
            trace_path = trace_dir / f"{agent_name}_trace.jsonl"
        self._cra_trace_path = Path(trace_path)
        self._cra_trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._cra_variant = {}
        variant_json = os.environ.get("CRADRIVE_VARIANT_JSON")
        if variant_json and Path(variant_json).exists():
            with open(variant_json, "r", encoding="utf-8") as f:
                self._cra_variant = json.load(f)
        self._cra_step = 0

    def _cra_get_hero(self):
        hero = getattr(self, "hero_actor", None)
        if hero is not None:
            return hero
        try:
            from srunner.scenariomanager.carla_data_provider import CarlaDataProvider
            world = CarlaDataProvider.get_world()
            for actor in world.get_actors():
                if actor.attributes.get("role_name") == "hero":
                    return actor
        except Exception:
            return None
        return None

    def _cra_world_snapshot(self):
        hero = self._cra_get_hero()
        if hero is None:
            return {"ego": None, "scenario_actors": []}

        tf = hero.get_transform()
        loc = tf.location
        vel = hero.get_velocity()
        acc = hero.get_acceleration()
        fwd = tf.get_forward_vector()
        right = tf.get_right_vector()
        ego_v_long = vel.x * fwd.x + vel.y * fwd.y + vel.z * fwd.z
        ego_speed = math.sqrt(vel.x**2 + vel.y**2 + vel.z**2)

        actors_out = []
        try:
            world = hero.get_world()
            actors = world.get_actors()
            for actor in actors:
                if actor.id == hero.id or actor.attributes.get("role_name") != "scenario":
                    continue
                atf = actor.get_transform()
                aloc = atf.location
                avel = actor.get_velocity()
                dx, dy, dz = aloc.x - loc.x, aloc.y - loc.y, aloc.z - loc.z
                euclid = math.sqrt(dx * dx + dy * dy + dz * dz)
                distance_2d = math.hypot(dx, dy)
                longitudinal = dx * fwd.x + dy * fwd.y + dz * fwd.z
                lateral = dx * right.x + dy * right.y + dz * right.z
                actor_v_long = avel.x * fwd.x + avel.y * fwd.y + avel.z * fwd.z
                closing_speed = ego_v_long - actor_v_long
                ttc = longitudinal / closing_speed if longitudinal > 0.0 and closing_speed > 0.05 else None
                rvx, rvy = avel.x - vel.x, avel.y - vel.y
                tcpa, dcpa = _cpa_2d(dx, dy, rvx, rvy)
                actors_out.append({
                    "id": int(actor.id),
                    "type_id": actor.type_id,
                    "location": _vec(aloc),
                    "velocity": _vec(avel),
                    "distance": float(euclid),
                    "distance_2d": float(distance_2d),
                    "relative_z": float(dz),
                    "longitudinal": float(longitudinal),
                    "lateral": float(lateral),
                    "actor_speed_longitudinal": float(actor_v_long),
                    "closing_speed": float(closing_speed),
                    "ttc_longitudinal": _finite(ttc),
                    "tcpa_2d": _finite(tcpa),
                    "dcpa_2d": _finite(dcpa),
                })
            # Do not use 3-D Euclidean distance for selection: Bench2Drive may keep
            # pedestrians underground before activation. Sort by on-plane 2-D distance.
            actors_out.sort(key=lambda a: (abs(a.get("relative_z", 0.0)) > 3.0, a.get("distance_2d", a["distance"])))
        except Exception:
            pass

        ego = {
            "location": _vec(loc),
            "rotation": [float(tf.rotation.roll), float(tf.rotation.pitch), float(tf.rotation.yaw)],
            "velocity": _vec(vel),
            "acceleration": _vec(acc),
            "speed": float(ego_speed),
            "speed_longitudinal": float(ego_v_long),
        }
        return {"ego": ego, "scenario_actors": actors_out}

    def _cra_log(self, timestamp, control, model_output=None, extra=None):
        snap = self._cra_world_snapshot()
        record = {
            "schema_version": 2,
            "run_id": self._cra_run_id,
            "pid": self._cra_pid,
            "seed": self._cra_seed,
            "agent": self._cra_agent_name,
            "step": int(getattr(self, "step", self._cra_step)),
            "timestamp": float(timestamp),
            "variant": self._cra_variant,
            "control": {
                "steer": float(control.steer),
                "throttle": float(control.throttle),
                "brake": float(control.brake),
            },
            **snap,
            "model_output": _jsonable(model_output or {}),
            "extra": _jsonable(extra or {}),
        }
        with open(self._cra_trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._cra_step += 1
