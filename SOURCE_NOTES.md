# Source inspection notes

CRADrive v0.1 was built against the two uploaded archives in this conversation.

## Bench2Drive 0.0.4

Relevant source points:

- `leaderboard/data/bench2drive_0.0.4_val.xml`
  - route `17749`, Town12: exactly one `DynamicObjectCrossing` scenario.
  - route `24519`, Town05: exactly one `ParkingCrossingPedestrian` scenario.
- `scenario_runner/srunner/scenarios/object_crash_vehicle.py`
  - `DynamicObjectCrossing` already reads `distance`, `crossing_angle`, `blocker_model`, and `direction` from XML.
  - its adversary speed, reaction time, and trigger distance are hard-coded in the uploaded source.
  - `ParkingCrossingPedestrian` similarly hard-codes adversary speed, reaction time, and trigger distance.
- `leaderboard/leaderboard/leaderboard_evaluator.py`
  - evaluator launches CARLA itself with `-RenderOffScreen` and the chosen `--gpu-rank`.
  - Traffic Manager seed is set explicitly.
- `leaderboard/leaderboard/utils/route_parser.py`
  - unrecognized scenario child tags are stored in `ScenarioConfiguration.other_parameters`, which is why adding `<reaction_time value="..."/>` is a minimal extension.

The patch is intentionally limited to reading those three values through the existing `get_value_parameter()` helper. Defaults are unchanged.

Uploaded source SHA256 used by the patch guard:

```text
c6168ffd0402bafc71375424aa755c3278f20c8544ef7fc50b315fec472e17f2  object_crash_vehicle.py
```

## DriveTransformer

Relevant source points:

- `team_code/drivetransformer_b2d_agent.py`
  - six camera inputs + IMU/GPS/speed are used.
  - model inference returns `ego_fut_preds_fix_time` and `ego_fut_preds_fix_dist`.
  - these predictions are passed directly into `DecouplePIDController.step(...)` before producing CARLA controls.
  - the official agent only saves lightweight PID metadata when its module-level `SAVE_PATH` is enabled; in the uploaded source it is hard-coded to `None`.

CRADrive therefore does not duplicate or edit the model. The wrapper replaces the **instance** `controller.step` with a closure that records exactly the trajectory arrays already being passed to the controller, then calls the original method. It also queries `CarlaDataProvider` after each base-agent step to record the ego and scenario actors.

Uploaded source SHA256 inspected:

```text
f957af41019b65db541c19fe3e0bfaf6bcb2e59c8175ce8d606bdde331f1a9c9  drivetransformer_b2d_agent.py
```
