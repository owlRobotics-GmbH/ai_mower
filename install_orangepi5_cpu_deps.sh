#!/usr/bin/env bash
set -euo pipefail

python_bin="${PYTHON_BIN:-python3}"

if command -v apt-get >/dev/null 2>&1; then
  echo "Installing system packages"
  sudo apt-get update
  sudo apt-get install -y \
    alsa-utils \
    can-utils \
    ffmpeg \
    iproute2 \
    python3-pip \
    python3-venv \
    v4l-utils
fi

echo "Using Python: $(${python_bin} --version)"
echo "Using pip: $(${python_bin} -m pip --version)"

arch="$(uname -m)"
if [[ "${arch}" != "aarch64" ]]; then
  echo "Warning: expected aarch64 for Orange Pi 5 / RK3588S, got ${arch}" >&2
fi

"${python_bin}" -m pip install --user --upgrade pip

# Runtime for detect_lawn.py without full TensorFlow or RKNN.
"${python_bin}" -m pip install --user \
  "tflite-runtime==2.14.0" \
  "rknn-toolkit-lite2==2.3.2"

# Training stack for train_texture.py on CPU.
# tensorflow==2.14.1 resolves to tensorflow-cpu-aws on aarch64 Linux.
"${python_bin}" -m pip install --user \
  "tensorflow==2.14.1" \
  "tensorflow-hub==0.15.0" \
  "tf2onnx==1.16.1"

echo
echo "Installed package check:"
"${python_bin}" - <<'PY'
mods = ["cv2", "numpy", "tflite_runtime", "tensorflow", "tensorflow_hub", "tf2onnx", "rknnlite.api", "rknn.api"]
for name in mods:
    try:
        mod = __import__(name)
        print(name, "OK", getattr(mod, "__version__", ""))
    except Exception as exc:
        print(name, "ERR", type(exc).__name__, exc)
PY
