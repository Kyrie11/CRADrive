"""CRADrive wrapper around the uploaded Bench2DriveZoo TCP agent."""
import importlib.util
import os
import sys
from pathlib import Path

from cradrive.agents.probe import CRAProbeMixin


def _load_base():
    repo = Path(os.environ["TCP_REPO"]).resolve()
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "team_code"))
    path = repo / "team_code" / "tcp_b2d_agent.py"
    spec = importlib.util.spec_from_file_location("cradrive_tcp_base", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = _load_base()


def get_entry_point():
    return "TCPCRAAgent"


class TCPCRAAgent(_BASE.TCPAgent, CRAProbeMixin):
    def setup(self, path_to_conf_file):
        super().setup(path_to_conf_file)
        self._cra_init("tcp")

    def run_step(self, input_data, timestamp):
        control = super().run_step(input_data, timestamp)
        meta = dict(getattr(self, "pid_metadata", {}) or {})
        # Normalize the field name used by downstream analysis.
        if "desired_speed" in meta:
            meta["planner_desired_speed"] = meta["desired_speed"]
        self._cra_log(timestamp, control, model_output=meta)
        return control
