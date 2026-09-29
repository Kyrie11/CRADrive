# Source adaptation notes (uploaded repositories)

## LEAD cvpr2026
- Official Bench2Drive entry: `scripts/eval_bench2drive.sh` -> `3rd_party/Bench2Drive/leaderboard/leaderboard/leaderboard_evaluator.py`.
- Official sensor agent: `lead/inference/sensor_agent.py` (`SensorAgent`).
- Checkpoint argument is a **directory**; the agent reads `config.json` and loads `model*.pth` from that directory.
- The evaluator appends `+<save_name>` to `--agent-config`; LEAD already strips the suffix in Bench2Drive mode, so the CRADrive wrapper preserves this behavior.
- Model output can be observed without editing LEAD by wrapping `self.closed_loop_inference.forward`. We log `pred_future_waypoints`, `pred_route`, and `pred_target_speed_scalar`.
- LEAD ships 220 route XMLs in `data/benchmark_routes/bench2drive`; v0.2 uses these as canonical routes so all agents receive byte-identical generated intervention XMLs.

## SimLingo
- Official agent: `team_code/agent_simlingo.py` (`LingoAgent`).
- Official Bench2Drive evaluator used by the uploaded code: `Bench2Drive/leaderboard/leaderboard/leaderboard_evaluator.py`.
- Checkpoint argument is the model state file such as `.../pytorch_model.pt`. The agent discovers its Hydra config relative to the checkpoint path.
- The evaluator appends `+<save_name>` to `--agent-config`; SimLingo explicitly parses this form.
- Model output can be observed without editing SimLingo by wrapping `self.model.forward`. We log predicted speed waypoints, route waypoints and language output.
- `ROUTES` and `SAVE_PATH` are exported by the v0.2 runner because SimLingo reads them during setup/logging.

## DriveTransformer
- v0.2 keeps the previous adapter approach: the base model is unmodified and the wrapper intercepts the PID controller input to record fixed-time/fixed-distance trajectory predictions.
- The external Bench2Drive evaluator remains the execution host, matching the path configuration used in v0.1.

## Bench2Drive scenario patch
The uploaded LEAD and SimLingo Bench2Drive copies contain the same `object_crash_vehicle.py` implementation/hash before patching. In that implementation `reaction_time`, adversary speed and minimum trigger distance are hard-coded for `DynamicObjectCrossing` / `ParkingCrossingPedestrian`. `ParkingCutIn` also hard-codes its reaction time.

`apply_semantic_patch_v2.py` only exposes these existing constants through `config.other_parameters`. With no XML override, defaults are unchanged. This is deliberately a scenario-instrumentation patch, not a policy modification.

## Why v0.1 was not sufficient
v0.1 was useful as a single-model instrumentation smoke test, but it could not strongly establish the research gap because:
1. it only tested DriveTransformer;
2. it treated the intervention parameter itself as the risk ordering without checking the actual closed-loop physical state;
3. its primary risk family was pedestrian release timing only;
4. nuisance controls and causal conditions were not analyzed across architectures;
5. it did not explicitly pre-register falsification gates.

v0.2 addresses these with three policy families, three semantic scenario families, activation-time physical-risk logging, appearance controls, and explicit H0-H6 gates.
