#!/usr/bin/env bash
set -euo pipefail
CKPT_ROOT="${1:-/data0/senzeyu2/dataset/CRADrive/checkpoints}"
mkdir -p "$CKPT_ROOT/tcp" "$CKPT_ROOT/simlingo"

if command -v hf >/dev/null 2>&1; then
  hf download rethinklab/Bench2DriveZoo tcp_b2d.ckpt --local-dir "$CKPT_ROOT/tcp"
  hf download RenzKa/simlingo --include 'simlingo/**' --local-dir "$CKPT_ROOT/simlingo"
else
  huggingface-cli download rethinklab/Bench2DriveZoo tcp_b2d.ckpt --local-dir "$CKPT_ROOT/tcp"
  huggingface-cli download RenzKa/simlingo --include 'simlingo/**' --local-dir "$CKPT_ROOT/simlingo"
fi

echo "TCP checkpoint: $CKPT_ROOT/tcp/tcp_b2d.ckpt"
echo "SimLingo snapshot root: $CKPT_ROOT/simlingo"
echo "Expected SimLingo agent config: $CKPT_ROOT/simlingo/simlingo/checkpoints/epoch=013.ckpt/pytorch_model.pt"
