# CRADrive v0.1 — causal-response pilot for Bench2Drive + DriveTransformer

This package implements the first **go/no-go experiment** for the research hypothesis:

> A high closed-loop driving score does not necessarily imply that a planner responds correctly to causally relevant visual/physical changes.

The implementation is deliberately minimal. It does **not** retrain DriveTransformer and does **not** perform image corruption. It creates paired Bench2Drive routes that differ in one semantic scenario parameter, logs DriveTransformer's predicted trajectories and controls, records scenario actors from CARLA, and summarizes response curves alongside the standard Bench2Drive score.

## What is modified

1. **Bench2Drive 0.0.4:** one reversible patch to `object_crash_vehicle.py` exposes three existing hard-coded quantities as XML parameters for `DynamicObjectCrossing` and `ParkingCrossingPedestrian`:
   - `reaction_time`
   - `adversary_speed`
   - `min_trigger_dist`

   Default values are unchanged, so the patch preserves the original behavior when the new XML fields are absent.

2. **DriveTransformer:** no source modification is required. `team_code/drivetransformer_cradrive_agent.py` subclasses the official agent, intercepts the PID controller input to log model trajectories, and logs CARLA world state.

## Why `reaction_time` is the first pilot variable

In the uploaded Bench2Drive source it is explicitly the *time the agent has to react to avoid the collision*. The baseline is hard-coded around 2.1–2.15 s. The pilot sweeps this variable while keeping the route, town, geometry, model, route command, and all other scenario parameters fixed.

This is a **diagnostic pilot**, not yet the final paper benchmark. A paper-level CRA claim should later replace/augment this proxy with a safety/expert causal-effect target and additional semantic interventions.

## Quick start

Run all commands in the **DriveTransformer conda environment**.

Do **not** separately launch a CARLA server for these commands. The uploaded Bench2Drive evaluator starts and stops its own `CarlaUE4.sh` process on the requested port. `CARLA_ROOT` should point to the installed CARLA directory.

```bash
export CRADRIVE=/path/to/CRADrive
export B2D_ROOT=/path/to/Bench2Drive-0.0.4
export DT_ROOT=/path/to/DriveTransformer
export CARLA_ROOT=/path/to/CARLA_0.9.15
export DT_CONFIG=$DT_ROOT/adzoo/drivetransformer/configs/drivetransformer/drivetransformer_large.py
export DT_CKPT=/path/to/drivetransformer_large.pth
```


## Shortest execution path

After exporting the six variables shown above, the full first-round workflow is:

```bash
bash $CRADRIVE/scripts/bootstrap_pilot.sh
bash $CRADRIVE/scripts/smoke_dt.sh
# inspect the smoke-test images/logs, then:
bash $CRADRIVE/scripts/run_dt_pilot.sh
bash $CRADRIVE/scripts/analyze_dt_pilot.sh
```

The sections below show the equivalent commands individually and explain what each step does.

### 1. Validate paths

```bash
python $CRADRIVE/scripts/validate_setup.py \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT" \
  --config "$DT_CONFIG" \
  --checkpoint "$DT_CKPT"
```

### 1b. Validate runtime imports in the active conda environment

```bash
python $CRADRIVE/scripts/preflight_runtime.py \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT"
```

This catches Python/CARLA/mmcv/py_trees path mismatches before a long CARLA launch.

### 2. Apply the small Bench2Drive patch

```bash
python $CRADRIVE/scripts/apply_b2d_patch.py --bench2drive "$B2D_ROOT"
```

The script checks the SHA256 of the uploaded Bench2Drive 0.0.4 file before changing it and creates:

```text
object_crash_vehicle.py.cradrive.bak
```

To revert:

```bash
python $CRADRIVE/scripts/apply_b2d_patch.py --bench2drive "$B2D_ROOT" --revert
```

### 3. Verify candidate routes

The uploaded Bench2Drive 0.0.4 validation XML contains particularly clean one-scenario routes:

- route `17749`: `DynamicObjectCrossing_1`
- route `24519`: `ParkingCrossingPedestrian_1`

List them yourself:

```bash
python $CRADRIVE/scripts/list_routes.py \
  --routes "$B2D_ROOT/leaderboard/data/bench2drive_0.0.4_val.xml" \
  --scenario-type DynamicObjectCrossing
```

### 4. Generate paired intervention routes

```bash
mkdir -p $CRADRIVE/experiments/pilot_dt
python $CRADRIVE/scripts/generate_pilot.py \
  --routes "$B2D_ROOT/leaderboard/data/bench2drive_0.0.4_val.xml" \
  --config "$CRADRIVE/configs/pilot.json" \
  --out "$CRADRIVE/experiments/pilot_dt"
```

The default config creates two causal sweeps plus negative-control weather variants. Every generated XML contains a **single original Bench2Drive route**; within a causal sweep, only `reaction_time` is changed.

### 5. Dry-run before spending GPU time

```bash
python $CRADRIVE/scripts/run_grid.py \
  --manifest "$CRADRIVE/experiments/pilot_dt/manifest.json" \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT" \
  --dt-config "$DT_CONFIG" \
  --dt-checkpoint "$DT_CKPT" \
  --out "$CRADRIVE/experiments/pilot_dt/runs" \
  --gpu 0 \
  --dry-run
```

`run_grid.py` creates `$B2D_ROOT/DriveTransformer -> $DT_ROOT` if the alias does not already exist. This matches the official DriveTransformer evaluation code's import convention.

### 6. First smoke test: one route only

Do this before the full grid:

```bash
python $CRADRIVE/scripts/run_grid.py \
  --manifest "$CRADRIVE/experiments/pilot_dt/manifest.json" \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT" \
  --dt-config "$DT_CONFIG" \
  --dt-checkpoint "$DT_CKPT" \
  --out "$CRADRIVE/experiments/pilot_dt/runs" \
  --gpu 0 \
  --only dynamic_crossing_reaction_time \
  --max-runs 1
```

Inspect:

```bash
find $CRADRIVE/experiments/pilot_dt/runs -maxdepth 2 -type f | sort
head -n 3 $CRADRIVE/experiments/pilot_dt/runs/*/trace.jsonl
cat $CRADRIVE/experiments/pilot_dt/runs/*/returncode.txt
```

A successful run should contain `trace.jsonl`, `checkpoint.json`, `stdout.log`, and `DONE`. For the first smoke test you may add `--save-images-every 10`; this saves front-camera and BEV JPEGs at 2 Hz so you can visually confirm that the semantic intervention activated as expected. Leave it off for the full grid to save disk.

### 7. Run the causal sweep first

Start with only the clean DynamicObjectCrossing route:

```bash
python $CRADRIVE/scripts/run_grid.py \
  --manifest "$CRADRIVE/experiments/pilot_dt/manifest.json" \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT" \
  --dt-config "$DT_CONFIG" \
  --dt-checkpoint "$DT_CKPT" \
  --out "$CRADRIVE/experiments/pilot_dt/runs" \
  --gpu 0 \
  --experiment dynamic_crossing_reaction_time \
  --kind causal
```

Then the second scenario family:

```bash
python $CRADRIVE/scripts/run_grid.py \
  --manifest "$CRADRIVE/experiments/pilot_dt/manifest.json" \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT" \
  --dt-config "$DT_CONFIG" \
  --dt-checkpoint "$DT_CKPT" \
  --out "$CRADRIVE/experiments/pilot_dt/runs" \
  --gpu 0 \
  --experiment parking_crossing_reaction_time \
  --kind causal
```

Run the weather negative controls after the causal sweeps:

```bash
python $CRADRIVE/scripts/run_grid.py \
  --manifest "$CRADRIVE/experiments/pilot_dt/manifest.json" \
  --bench2drive "$B2D_ROOT" \
  --drivetransformer "$DT_ROOT" \
  --carla "$CARLA_ROOT" \
  --dt-config "$DT_CONFIG" \
  --dt-checkpoint "$DT_CKPT" \
  --out "$CRADRIVE/experiments/pilot_dt/runs" \
  --gpu 0 \
  --kind nuisance_weather
```

The script skips conditions with a `DONE` marker, so rerunning is safe. Use `--overwrite` only when you intentionally want to discard an existing run.

### 8. Analyze

```bash
python $CRADRIVE/scripts/analyze_pilot.py \
  --manifest "$CRADRIVE/experiments/pilot_dt/manifest.json" \
  --runs "$CRADRIVE/experiments/pilot_dt/runs" \
  --out "$CRADRIVE/experiments/pilot_dt/analysis"
```

Primary outputs:

```text
analysis/summary.csv
analysis/report.md
analysis/*__min_speed_near_hazard_mps.png
analysis/*__max_brake_near_hazard.png
analysis/*__driving_score.png
analysis/*__min_dynamic_actor_distance_m.png
analysis/*__speed_mps_vs_actor_distance.png
analysis/*__brake_vs_actor_distance.png
```

## What to look for

The most interesting preliminary finding is **not** simply a collision at the hardest setting. Look for one of these:

- similar Bench2Drive score across conditions but clearly different/irregular physical response;
- a flat response to a meaningful change in available reaction time;
- discontinuous or non-monotonic braking/speed behavior;
- negative-control weather causing a response of comparable magnitude to the physical intervention;
- predicted-trajectory changes that do not agree with the eventual control response.

A weak result is: smooth, stable, semantically sensible response curves; nuisance changes have little effect; and the new diagnostics contain almost no information beyond standard score. If that happens consistently across DriveTransformer plus two other model families, this exact thesis should be reconsidered rather than forced.

## Important interpretation note

`reaction_time` is a controlled semantic parameter already used internally by the Bench2Drive scenario implementation, but it is **not yet an expert causal-effect oracle**. For a paper-level benchmark, the next phase should add explicit conflict-point geometry / TTC targets or an expert controller and compute a true Causal Response Alignment target. The current package is for deciding whether that investment is justified.

## Tests that do not require CARLA

```bash
cd $CRADRIVE
python -m unittest tests/test_xml_tools.py -v
```
