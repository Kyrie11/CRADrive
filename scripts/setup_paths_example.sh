#!/usr/bin/env bash
# Edit these paths once, then: source scripts/setup_paths_example.sh
export CRADRIVE_ROOT=/home/senzeyu2/code/CRADrive
export CRADRIVE_DATA=/data0/senzeyu2/dataset/CRADrive
export B2D_ROOT=/home/senzeyu2/code/Bench2Drive-0.0.4
export TCP_REPO=/home/senzeyu2/code/Bench2DriveZoo-tcp-admlp
export SIMLINGO_REPO=/home/senzeyu2/code/simlingo
export CARLA_ROOT=/data0/senzeyu2/dataset/CRADrive/CARLA_0.9.15
export TCP_CKPT=$CRADRIVE_DATA/checkpoints/tcp/tcp_b2d.ckpt
export SIMLINGO_CKPT=$CRADRIVE_DATA/checkpoints/simlingo/simlingo/checkpoints/epoch=013.ckpt/pytorch_model.pt
export PYTHONPATH=$CRADRIVE_ROOT:${PYTHONPATH:-}
