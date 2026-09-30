
# Build helpers used by flash-attn.
conda run -n simlingo python -m pip install -U packaging ninja wheel

SIMLINGO_PREFIX="$(conda run -n simlingo python -c 'import sys; print(sys.prefix)')"

echo "SimLingo prefix: $SIMLINGO_PREFIX"
CUDA_HOME="$SIMLINGO_PREFIX" PATH="$SIMLINGO_PREFIX/bin:$PATH" \
  conda run -n simlingo bash -c '
    echo "nvcc: $(command -v nvcc)"
    nvcc -V
    python -c "import torch; print(\"torch:\", torch.__version__); print(\"torch CUDA:\", torch.version.cuda); print(\"CUDA available:\", torch.cuda.is_available())"
  '

# Limit parallel jobs to reduce peak RAM use while compiling.
CUDA_HOME="$SIMLINGO_PREFIX" PATH="$SIMLINGO_PREFIX/bin:$PATH" MAX_JOBS="${MAX_JOBS:-4}" \
  conda run -n simlingo python -m pip install \
  'flash-attn==2.7.0.post2' --no-build-isolation --no-cache-dir

# -------------------------
# CRA-Drive / TCP environment
# -------------------------
if ! conda env list | awk '{print $1}' | grep -qx cradrive-tcp; then
  conda create -y -n cradrive-tcp python=3.8 pip
fi

conda run -n cradrive-tcp python -m pip install \
  numpy==1.23.5 scipy pillow opencv-python matplotlib imgaug \
  'torch==2.2.0' 'torchvision==0.17.0' \
  py-trees==0.8.3 simple-watchdog-timer shapely==1.7.1 ephem tabulate \
  dictor requests pygame pexpect transforms3d xmlschema networkx==3.1 psutil six \
  carla==0.9.15

# Basic verification.
CUDA_HOME="$SIMLINGO_PREFIX" PATH="$SIMLINGO_PREFIX/bin:$PATH" \
  conda run -n simlingo python -c 'import torch, flash_attn; print("torch", torch.__version__, "CUDA", torch.version.cuda); print("flash_attn", flash_attn.__version__)'

echo "Ready envs: simlingo, cradrive-tcp"