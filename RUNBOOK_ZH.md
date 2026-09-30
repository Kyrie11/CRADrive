# CRADrive Pilot 运行手册

## 0. 推荐目录

```bash
/home/senzeyu2/code/CRADrive
/home/senzeyu2/code/Bench2Drive-0.0.4
/home/senzeyu2/code/Bench2DriveZoo-tcp-admlp
/home/senzeyu2/code/simlingo
/data0/senzeyu2/dataset/CRADrive/
  CARLA_0.9.15/
  checkpoints/
  routes_v1/
  runs_v1/
  analysis_v1/
```

## 1. 配置路径

编辑 `scripts/setup_paths_example.sh` 后：

```bash
source /home/senzeyu2/code/CRADrive/scripts/setup_paths_example.sh
```

## 2. CARLA 0.9.15

```bash
bash $CRADRIVE_ROOT/scripts/install_carla_0915.sh $CRADRIVE_DATA/CARLA_0.9.15
$CARLA_ROOT/CarlaUE4.sh -RenderOffScreen -nosound -carla-rpc-port=2000
```

另开终端确认 CARLA 能正常启动后 Ctrl-C。Bench2Drive evaluator 会自行启动 CARLA。

## 3. Python 环境

SimLingo 首先严格使用其上传源码中的 `environment.yaml`：

```bash
source $CRADRIVE_ROOT/scripts/setup_paths_example.sh
bash $CRADRIVE_ROOT/scripts/create_envs.sh
```

若 `flash-attn` 编译失败，先确认 `nvcc --version` 与 PyTorch CUDA 版本兼容。不要为了装 flash-attn 随意升级 transformers/torch。

### 3.1 强制检查 benchmark 版本（很重要）

在每个运行环境里都执行一次：

```bash
source $CRADRIVE_ROOT/scripts/setup_paths_example.sh
export SCENARIO_RUNNER_ROOT=$B2D_ROOT/scenario_runner
export PYTHONPATH=$B2D_ROOT/leaderboard:$B2D_ROOT/scenario_runner:$CRADRIVE_ROOT:$PYTHONPATH
python $CRADRIVE_ROOT/tools/check_runtime_imports.py --expect-b2d $B2D_ROOT
```

输出的 `leaderboard` 和 `srunner` 路径必须来自 `$B2D_ROOT`，不能来自 `$SIMLINGO_REPO/Bench2Drive`。`run_one.sh` 已经按这个优先级设置 `PYTHONPATH`。

TCP 若单独环境依赖冲突，也可以直接在 `simlingo` 环境里先做 TCP smoke test；TCP 闭环推理本身不依赖其训练脚本中的 PyTorch-Lightning。

## 4. checkpoint

```bash
conda activate simlingo
pip install -U huggingface_hub
bash $CRADRIVE_ROOT/scripts/download_checkpoints.sh $CRADRIVE_DATA/checkpoints
```

TCP: `$CRADRIVE_DATA/checkpoints/tcp/tcp_b2d.ckpt`。

SimLingo 下载整个 Hugging Face `simlingo/**` 目录，因为 agent 除 `pytorch_model.pt` 外还会从 checkpoint 上层读取 Hydra 配置。默认运行手册使用：

```bash
$CRADRIVE_DATA/checkpoints/simlingo/simlingo/checkpoints/epoch=013.ckpt/pytorch_model.pt
```

如果 Hugging Face 当前目录中的 epoch 名称不同，用实际 checkpoint 的 `pytorch_model.pt` 修改 `SIMLINGO_CKPT`。

## 5. 安装自定义 scenario plugin

```bash
source $CRADRIVE_ROOT/scripts/setup_paths_example.sh
bash $CRADRIVE_ROOT/scripts/install_b2d_plugin.sh
```

这一步只新增 `scenario_runner/srunner/scenarios/cra_interventions.py`，不覆盖 Bench2Drive 原始 scenario。

## 6. 生成 matched routes

```bash
mkdir -p $CRADRIVE_DATA/routes_v1
python $CRADRIVE_ROOT/tools/generate_routes.py \
  --b2d-root $B2D_ROOT \
  --out $CRADRIVE_DATA/routes_v1

python $CRADRIVE_ROOT/tools/check_matched.py \
  $CRADRIVE_DATA/routes_v1/manifest.jsonl
```

应看到 34 个 route variants，且每个 family/route 的 canonical matched check 都是 `OK`。

## 7. 先跑最小 smoke test（TCP）

```bash
conda activate cradrive-tcp
source $CRADRIVE_ROOT/scripts/setup_paths_example.sh

ROUTE=$CRADRIVE_DATA/routes_v1/pedestrian_reaction_time/route_13674/rt3p5/route.xml
META=$CRADRIVE_DATA/routes_v1/pedestrian_reaction_time/route_13674/rt3p5/variant.json
bash $CRADRIVE_ROOT/scripts/run_one.sh tcp "$ROUTE" "$META" \
  $CRADRIVE_DATA/runs_v1/tcp/smoke 1 0
```

确认以下文件存在且非空：

```bash
ls -lh $CRADRIVE_DATA/runs_v1/tcp/smoke/{result.json,trace.jsonl,stdout.log}
head -n 2 $CRADRIVE_DATA/runs_v1/tcp/smoke/trace.jsonl
```

`trace.jsonl` 中应看到 `model_output.planner_desired_speed`、`ego.speed`、`scenario_actors[*].distance/closing_speed/ttc_longitudinal`。

## 8. 跑 pedestrian 第一条决定性曲线

先只跑一个 route、五个 severity；最省时间的做法是临时建立过滤后的 manifest，或直接依次执行五个目录。若基础链路稳定，再跑完整 family：

```bash
conda activate cradrive-tcp
source $CRADRIVE_ROOT/scripts/setup_paths_example.sh
python $CRADRIVE_ROOT/scripts/run_suite.py \
  --manifest $CRADRIVE_DATA/routes_v1/manifest.jsonl \
  --agent tcp \
  --families pedestrian_reaction_time \
  --seeds 1,2,3 \
  --out $CRADRIVE_DATA/runs_v1 \
  --skip-existing
```

## 9. SimLingo

```bash
conda activate simlingo
source $CRADRIVE_ROOT/scripts/setup_paths_example.sh
python $CRADRIVE_ROOT/scripts/run_suite.py \
  --manifest $CRADRIVE_DATA/routes_v1/manifest.jsonl \
  --agent simlingo \
  --families pedestrian_reaction_time \
  --seeds 1,2,3 \
  --out $CRADRIVE_DATA/runs_v1 \
  --skip-existing
```

SimLingo wrapper 不修改网络输出，只重载 `control_pid` 以记录传给原 controller 的 `pred_route`、`pred_speed_waypoints` 和按原公式计算的 `planner_desired_speed`，然后仍调用原 `control_pid`。

## 10. 初步分析

```bash
python $CRADRIVE_ROOT/cradrive/analysis/summarize.py \
  --runs $CRADRIVE_DATA/runs_v1 \
  --out $CRADRIVE_DATA/analysis_v1

python $CRADRIVE_ROOT/cradrive/analysis/plot_curves.py \
  --summary $CRADRIVE_DATA/analysis_v1/run_summary.csv \
  --out $CRADRIVE_DATA/analysis_v1/figures
```

第一张关键图：x=intervention risk rank；y=min planner desired speed。风险升高时合理趋势应为 desired speed 不增。`monotonicity_report.json` 用 0.25 m/s 容差标记明显反向变化；最终论文前应做更严格的事件对齐和统计，而不是直接把这个 pilot 阈值作为正式 metric。

## 11. 推荐执行顺序（GO/STOP）

1. TCP smoke test：只验证 infrastructure。
2. SimLingo + pedestrian reaction-time：这是第一个真正 scientific gate。
3. 若出现可重复 delayed/non-monotonic response，再跑 pedestrian direction control，排除“只是视觉显著性”的解释。
4. 再跑 HighwayCutIn，判断现象是否跨 scenario family。
5. 此时再接 TFv6；不要在 hypothesis 尚未成立前花时间实现 CRA training。

## 12. 当前 pilot 的解释边界

`ttc_longitudinal` 是基于 ego forward axis 的近似纵向 TTC，对横穿行人不是严格 collision TTC。因此 pedestrian 主 causal x-axis 应先用 controlled `reaction_time/risk_rank`，并用 actor distance/trajectory 做 sanity check。后续正式 benchmark 应实现 geometry-aware closest-approach / PET oracle。
