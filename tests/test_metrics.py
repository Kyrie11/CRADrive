import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cradrive.metrics import summarize_trace


class MetricsTest(unittest.TestCase):
    def test_prefers_walker_and_localizes_hazard(self):
        rows = [
            {"step": 0, "speed_mps": 0.0, "control": {"brake": 1.0}, "scenario_actors": []},
            {"step": 30, "speed_mps": 8.0, "control": {"brake": 0.0}, "scenario_actors": [
                {"type_id": "vehicle.audi.a2", "distance_m": 5.0, "longitudinal_m": 5.0, "velocity": [0,0,0]},
                {"type_id": "walker.pedestrian.0001", "distance_m": 25.0, "longitudinal_m": 25.0, "velocity": [1,0,0]},
            ]},
            {"step": 31, "speed_mps": 5.0, "control": {"brake": 0.8}, "scenario_actors": [
                {"type_id": "vehicle.audi.a2", "distance_m": 4.0, "longitudinal_m": 4.0, "velocity": [0,0,0]},
                {"type_id": "walker.pedestrian.0001", "distance_m": 10.0, "longitudinal_m": 10.0, "velocity": [1,0,0]},
            ]},
        ]
        s = summarize_trace(rows)
        self.assertEqual(s["min_speed_near_hazard_mps"], 5.0)
        self.assertEqual(s["max_brake_near_hazard"], 0.8)
        self.assertEqual(s["min_dynamic_actor_distance_m"], 10.0)


if __name__ == "__main__":
    unittest.main()
