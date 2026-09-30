#!/usr/bin/env bash
set -euo pipefail
DEST="${1:-/data0/senzeyu2/dataset/CRADrive/CARLA_0.9.15}"
mkdir -p "$DEST"
cd "$DEST"
if [[ ! -f CarlaUE4.sh ]]; then
  wget -c https://carla-releases.s3.us-east-005.backblazeb2.com/Linux/CARLA_0.9.15.tar.gz
  tar -xzf CARLA_0.9.15.tar.gz
fi
if [[ ! -f Import/AdditionalMaps_0.9.15.tar.gz ]]; then
  mkdir -p Import
  wget -c -O Import/AdditionalMaps_0.9.15.tar.gz https://carla-releases.s3.us-east-005.backblazeb2.com/Linux/AdditionalMaps_0.9.15.tar.gz
fi
bash ImportAssets.sh
echo "CARLA installed at $DEST"
