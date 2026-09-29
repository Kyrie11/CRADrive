# CRADrive v0.2 — multi-model causal-grounding pilot

v0.2 keeps the v0.1 idea but makes four changes required for a defensible research decision:

1. identical canonical route XML is used for all models;
2. three model families are supported without modifying their model source;
3. the trace contains privileged physical-risk quantities (CPA/TTC/required stopping deceleration), not only the intervention parameter;
4. hypotheses and GO/NO-GO criteria are pre-specified in `HYPOTHESES.md`.

## Expected paths
Keep the previous variables:

```bash
export CRADRIVE=/path/to/CRADrive_v0.2
export B2D_ROOT=/path/to/Bench2Drive-0.0.4
export DT_ROOT=/path/to/DriveTransformer
export CARLA_ROOT=/path/to/CARLA_0.9.15
export DT_CONFIG=$DT_ROOT/adzoo/drivetransformer/configs/drivetransformer/drivetransformer_large.py
export DT_CKPT=/path/to/drivetransformer_checkpoint.pth
```

Add:

```bash
export LEAD_ROOT=/path/to/lead-cvpr2026
export LEAD_CKPT=/path/to/lead/checkpoint_directory
export SIMLINGO_ROOT=/path/to/simlingo-main
export SIMLINGO_CKPT=/path/to/pytorch_model.pt
```

Use LEAD's CVPR2026 220-route set as the canonical XML source:

```bash
export CRADRIVE_ROUTE_DIR=$LEAD_ROOT/data/benchmark_routes/bench2drive
```

## One-time semantic patch
The model code is left untouched. The patch only exposes scenario-runner timing parameters already hard-coded in Bench2Drive.

```bash
python $CRADRIVE/scripts/apply_semantic_patch_v2.py \
  --bench2drive $B2D_ROOT \
  --bench2drive $LEAD_ROOT/3rd_party/Bench2Drive \
  --bench2drive $SIMLINGO_ROOT/Bench2Drive
```

## Generate an identical intervention matrix

```bash
mkdir -p $CRADRIVE/experiments/pilot_v2
python $CRADRIVE/scripts/generate_matrix_v2.py \
  --route-dir $CRADRIVE_ROUTE_DIR \
  --config $CRADRIVE/configs/pilot_v2.json \
  --out $CRADRIVE/experiments/pilot_v2
```

Default decisive pilot = 3 routes per scenario × (5 causal + 2 appearance controls) × 3 scenario families = 63 conditions per model per seed. For an initial smoke use `--routes-per-scenario 1` and then `--max-runs` in the runner.

## Run DriveTransformer (inside its conda env)

```bash
conda activate <your_dt_env>
python $CRADRIVE/scripts/run_model_grid_v2.py \
  --model dt \
  --manifest $CRADRIVE/experiments/pilot_v2/manifest.json \
  --out $CRADRIVE/experiments/pilot_v2/runs_dt \
  --carla $CARLA_ROOT --root $DT_ROOT --bench2drive $B2D_ROOT \
  --checkpoint $DT_CKPT --dt-config $DT_CONFIG \
  --gpu 0 --seeds 0
```

Smoke example: append `--only dynamic_ped_release_tta --max-runs 3`.

## Run LEAD CVPR2026 (inside the LEAD env)

```bash
conda activate <your_lead_env>
cd $LEAD_ROOT
python $CRADRIVE/scripts/run_model_grid_v2.py \
  --model lead \
  --manifest $CRADRIVE/experiments/pilot_v2/manifest.json \
  --out $CRADRIVE/experiments/pilot_v2/runs_lead \
  --carla $CARLA_ROOT --root $LEAD_ROOT --checkpoint $LEAD_CKPT \
  --gpu 0 --seeds 0
```

`LEAD_CKPT` is the directory containing its `config.json` and `model*.pth`, matching the official `scripts/eval_bench2drive.sh` convention.

## Run SimLingo (inside its own env)

```bash
conda activate <your_simlingo_env>
cd $SIMLINGO_ROOT
python $CRADRIVE/scripts/run_model_grid_v2.py \
  --model simlingo \
  --manifest $CRADRIVE/experiments/pilot_v2/manifest.json \
  --out $CRADRIVE/experiments/pilot_v2/runs_simlingo \
  --carla $CARLA_ROOT --root $SIMLINGO_ROOT --checkpoint $SIMLINGO_CKPT \
  --gpu 0 --seeds 0
```

## Analyze all three together
Use any environment with plain Python; matplotlib is optional.

```bash
python $CRADRIVE/scripts/analyze_multimodel_v2.py \
  --manifest $CRADRIVE/experiments/pilot_v2/manifest.json \
  --model-run dt=$CRADRIVE/experiments/pilot_v2/runs_dt \
  --model-run lead=$CRADRIVE/experiments/pilot_v2/runs_lead \
  --model-run simlingo=$CRADRIVE/experiments/pilot_v2/runs_simlingo \
  --out $CRADRIVE/experiments/pilot_v2/analysis
```

Read `analysis/hypothesis_report.md` first and `analysis/summary.csv` second.

## Recommended staged compute
1. **Adapter smoke:** `routes-per-scenario=1`, one model, three values.
2. **Cross-model smoke:** same one route and 3 values on all three models.
3. **Decision pilot:** 3 routes/scenario, all 5 values, seed 0.
4. Only if GO: repeat with `--seeds 0,1,2` and then expand intervention families.

Do not spend compute on training CRA before stage 3 passes the GO gate.

## Preflight all paths

```bash
python $CRADRIVE/scripts/preflight_v2.py \
  --carla $CARLA_ROOT --bench2drive $B2D_ROOT \
  --dt-root $DT_ROOT --dt-config $DT_CONFIG --dt-checkpoint $DT_CKPT \
  --lead-root $LEAD_ROOT --lead-checkpoint $LEAD_CKPT \
  --simlingo-root $SIMLINGO_ROOT --simlingo-checkpoint $SIMLINGO_CKPT
```
