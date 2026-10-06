"""CRADrive wrapper around SimLingo with direct waypoint/desired-speed logging."""
import importlib.util
import os
import sys
from pathlib import Path

import numpy as np

from cradrive.agents.probe import CRAProbeMixin


def _load_base():
    repo = Path(os.environ["SIMLINGO_REPO"]).resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "team_code"))
    path = repo / "team_code" / "agent_simlingo.py"
    spec = importlib.util.spec_from_file_location("cradrive_simlingo_base", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = _load_base()


def get_entry_point():
    return "SimLingoCRAAgent"


class SimLingoCRAAgent(_BASE.LingoAgent, CRAProbeMixin):
    def setup(self, path_to_conf_file, route_index=None):
        super().setup(path_to_conf_file, route_index=route_index)
        self._cra_init("simlingo")
        self._cra_last_model_output = {}

    def control_pid(self, route_waypoints, velocity, speed_waypoints):
        # Capture the exact planner outputs used by the original controller without
        # changing the action computation.
        out = {}
        try:
            route_np = route_waypoints[0].detach().float().cpu().numpy()
            speed_wp_np = speed_waypoints[0].detach().float().cpu().numpy()
            out["pred_route"] = route_np.tolist()
            out["pred_speed_waypoints"] = speed_wp_np.tolist()
            one_second = int(self.config.carla_fps // (self.config.wp_dilation * self.config.data_save_freq))
            half_second = one_second // 2
            i0 = max(0, half_second - 2)
            i1 = max(0, one_second - 2)
            if len(speed_wp_np) > max(i0, i1):
                desired_speed = np.linalg.norm(speed_wp_np[i0] - speed_wp_np[i1]) * 2.0
                out["planner_desired_speed"] = float(desired_speed)
        except Exception as exc:
            out["capture_error"] = repr(exc)
        self._cra_last_model_output = out
        return super().control_pid(route_waypoints, velocity, speed_waypoints)

    def run_step(self, input_data, timestamp, sensors=None):
        control = super().run_step(input_data, timestamp, sensors=sensors)
        self._cra_log(timestamp, control, model_output=self._cra_last_model_output)
        return control

    def destroy(self, results=None):
        # SimLingo's upstream destroy() assumes cfg.data_module.encoder exists.
        # Some released evaluation configs do not contain that key, which can raise
        # during leaderboard cleanup *after* a completed route and prevent the
        # checkpoint from being finalized. Upstream destroy only releases these
        # heavy objects, so do the same defensively here.
        for name in ("model", "config", "processor"):
            if hasattr(self, name):
                try:
                    delattr(self, name)
                except Exception:
                    pass
        try:
            import gc
            gc.collect()
        except Exception:
            pass
