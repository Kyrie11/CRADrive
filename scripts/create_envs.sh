#!/usr/bin/env bash
set -euo pipefail
: "${SIMLINGO_REPO:?set SIMLINGO_REPO}"

if ! conda env list | awk '{print $1}' | grep -qx simlingo; then
  conda env create -f "$SIMLINGO_REPO/environment.yaml"
fi
conda run -n simlingo pip install 'torch==2.2.0' 'torchvision==0.17.0' 'torchaudio==2.2.0'
# Official SimLingo setup installs this separately. Requires a compatible CUDA toolkit/nvcc.
conda run -n simlingo pip install 'flash-attn==2.7.0.post2' --no-build-isolation

if ! conda env list | awk '{print $1}' | grep -qx cradrive-tcp; then
  conda create -y -n cradrive-tcp python=3.8 pip
fi
conda run -n cradrive-tcp pip install \
  numpy==1.23.5 scipy pillow opencv-python matplotlib imgaug \
  'torch==2.2.0' 'torchvision==0.17.0' \
  py-trees==0.8.3 simple-watchdog-timer shapely==1.7.1 ephem tabulate \
  dictor requests pygame pexpect transforms3d xmlschema networkx==3.1 psutil six \
  carla==0.9.15

echo "Ready envs: simlingo, cradrive-tcp"
