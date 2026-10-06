"""CRADrive wrapper for LEAD's *cvpr2026* SensorAgent / TFv6.

This wrapper is intentionally thin: it leaves LEAD's policy, controllers and optional
post-processing heuristics unchanged.  It only captures the closed-loop prediction
returned by ``ClosedLoopInference.forward`` and appends CRADrive's privileged world
snapshot for post-hoc analysis.

Expected upstream branch: https://github.com/kesai-labs/lead/tree/cvpr2026
Do not use this adapter with LEAD ``main``; the two branches are independent.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from cradrive.agents.probe import CRAProbeMixin


def _load_sensor_agent():
    repo = Path(os.environ["LEAD_CVPR_REPO"]).resolve()
    if not (repo / "lead" / "inference" / "sensor_agent.py").exists():
        raise RuntimeError(
            f"LEAD_CVPR_REPO={repo} does not look like the cvpr2026 checkout "
            "(missing lead/inference/sensor_agent.py)"
        )
    sys.path.insert(0, str(repo))
    from lead.inference.sensor_agent import SensorAgent  # type: ignore
    return SensorAgent


_SENSOR_AGENT = _load_sensor_agent()


def get_entry_point():
    return "LEADCVPRCRAAgent"


def _scalar(x):
    if x is None:
        return None
    try:
        import torch
        if torch.is_tensor(x):
            return float(x.detach().float().reshape(-1)[0].cpu().item())
    except Exception:
        pass
    try:
        return float(x)
    except Exception:
        return None


class LEADCVPRCRAAgent(_SENSOR_AGENT, CRAProbeMixin):
    """TFv6 agent with non-invasive planner-output logging."""

    def setup(self, path_to_conf_file, *args, **kwargs):
        super().setup(path_to_conf_file, *args, **kwargs)
        self._cra_init("lead_tfv6")
        self._cra_last_prediction = None

        # Capture the prediction before SensorAgent's stop-sign / force-move
        # post-processing modifies the executed control.  This lets the analysis
        # separate planner response from downstream heuristics.
        original_forward = self.closed_loop_inference.forward

        def _capturing_forward(*fargs, **fkwargs):
            pred = original_forward(*fargs, **fkwargs)
            self._cra_last_prediction = pred
            return pred

        self.closed_loop_inference.forward = _capturing_forward

    def _cra_prediction_dict(self):
        p = self._cra_last_prediction
        if p is None:
            return {}
        out = {
            "planner_desired_speed": _scalar(getattr(p, "pred_target_speed_scalar", None)),
            "pred_target_speed_scalar": getattr(p, "pred_target_speed_scalar", None),
            "pred_target_speed_distribution": getattr(p, "pred_target_speed_distribution", None),
            "pred_future_waypoints": getattr(p, "pred_future_waypoints", None),
            "pred_route": getattr(p, "pred_route", None),
            # Controls produced by LEAD's closed-loop inference before SensorAgent's
            # optional force-move / stop-sign post-processors.
            "pre_postprocess_steer": getattr(p, "steer", None),
            "pre_postprocess_throttle": getattr(p, "throttle", None),
            "pre_postprocess_brake": getattr(p, "brake", None),
            "target_speed_throttle": getattr(p, "target_speed_throttle", None),
            "target_speed_brake": getattr(p, "target_speed_brake", None),
        }
        return out

    def run_step(self, input_data, timestamp, *args, **kwargs):
        control = super().run_step(input_data, timestamp, *args, **kwargs)
        self._cra_log(
            timestamp,
            control,
            model_output=self._cra_prediction_dict(),
            extra={
                "lead_step": getattr(self, "step", None),
                "lead_creeping_enabled": getattr(getattr(self, "config_closed_loop", None), "sensor_agent_creeping", None),
                "lead_stop_sign_heuristic_enabled": getattr(getattr(self, "config_closed_loop", None), "slower_for_stop_sign", None),
                "lead_kalman_enabled": getattr(getattr(self, "config_closed_loop", None), "use_kalman_filter", None),
            },
        )
        return control
