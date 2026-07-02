#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: ./run.sh

Environment:
  PYTHON_BIN              Python interpreter used when creating the venv.
  VENV_DIR                Virtual environment directory. Default: .venv
  REQUIREMENTS_FILE       Requirements file. Default: requirements.txt
  REQUIRED_PYTHON_MINOR   Optional Python minor version guard, for example 3.11.
  AI_MOWER_SEGMENTATION_BACKEND
                          auto, onnx, rknn, or transformers. Default: auto.
                          auto prefers ONNX on laptop and RKNN on RK3588.
  AI_MOWER_RKNN_RUNTIME_INSTALL
                          auto installs vendor/rknn_runtime/lib/librknnrt.so
                          when data/segmentation/model.rknn exists and the
                          system librknnrt differs. Set 0 to disable.

OrangePi-like local test matrix example:
  PYTHON_BIN=python3.11 \
  REQUIRED_PYTHON_MINOR=3.11 \
  VENV_DIR=.venv-py3.11 \
  REQUIREMENTS_FILE=requirements_orangepi_cpu.txt \
  ./run.sh
EOF
  exit 0
fi

python_bin="${PYTHON_BIN:-python3}"
venv_dir="${VENV_DIR:-.venv}"
requirements_file="${REQUIREMENTS_FILE:-requirements.txt}"
required_python_minor="${REQUIRED_PYTHON_MINOR:-}"
venv_python="${venv_dir}/bin/python"
deps_stamp="${venv_dir}/.requirements-installed"
rknn_runtime_install="${AI_MOWER_RKNN_RUNTIME_INSTALL:-auto}"
rknn_runtime_source="${AI_MOWER_RKNN_RUNTIME_SOURCE:-vendor/rknn_runtime/lib/librknnrt.so}"
rknn_runtime_system="${AI_MOWER_RKNN_RUNTIME_SYSTEM:-/lib/librknnrt.so}"
segmentation_backend="${AI_MOWER_SEGMENTATION_BACKEND:-auto}"

librknn_version() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    strings "${path}" 2>/dev/null | sed -n 's/^librknnrt version: //p' | head -n 1
  fi
}

is_rk3588_platform() {
  if [[ "$(uname -m)" != "aarch64" ]]; then
    return 1
  fi
  if [[ -r /proc/device-tree/compatible ]] && tr '\0' '\n' < /proc/device-tree/compatible | grep -qi 'rk3588'; then
    return 0
  fi
  [[ "$(hostname)" == *orangepi* ]]
}

ensure_rknn_runtime() {
  if [[ "${rknn_runtime_install}" =~ ^(0|false|no|off)$ ]]; then
    return
  fi
  if [[ "${segmentation_backend}" != "rknn" ]] && ! is_rk3588_platform; then
    return
  fi
  if [[ ! -f "data/segmentation/model.rknn" || ! -f "${rknn_runtime_source}" ]]; then
    return
  fi

  local source_version system_version version_id target_path backup_path
  source_version="$(librknn_version "${rknn_runtime_source}")"
  system_version="$(librknn_version "${rknn_runtime_system}")"
  if [[ -z "${source_version}" ]]; then
    echo "RKNN runtime source has no readable version: ${rknn_runtime_source}" >&2
    return
  fi
  if [[ "${source_version}" == "${system_version}" ]]; then
    echo "RKNN runtime: ${system_version}"
    return
  fi
  if [[ "${rknn_runtime_install}" != "auto" && ! "${rknn_runtime_install}" =~ ^(1|true|yes|on)$ ]]; then
    return
  fi

  version_id="$(printf '%s' "${source_version}" | awk '{print $1}')"
  target_path="${rknn_runtime_system}.${version_id}"
  echo "RKNN runtime mismatch:"
  echo "  system: ${system_version:-missing}"
  echo "  source: ${source_version}"
  echo "Installing RKNN runtime via sudo: ${target_path}"

  if [[ -e "${rknn_runtime_system}" && ! -L "${rknn_runtime_system}" ]]; then
    backup_path="${rknn_runtime_system}.${system_version%% *}.bak"
    if [[ ! -e "${backup_path}" ]]; then
      sudo cp -a "${rknn_runtime_system}" "${backup_path}"
      echo "Backed up old RKNN runtime to ${backup_path}"
    fi
  fi
  sudo install -m 0644 "${rknn_runtime_source}" "${target_path}"
  sudo ln -sf "$(basename "${target_path}")" "${rknn_runtime_system}"
  sudo ldconfig
  echo "RKNN runtime installed: $(librknn_version "${rknn_runtime_system}")"
}

if [[ -n "${required_python_minor}" ]]; then
  actual_python_minor="$("${python_bin}" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
  if [[ "${actual_python_minor}" != "${required_python_minor}" ]]; then
    echo "Python ${required_python_minor} is required, but ${python_bin} is Python ${actual_python_minor}." >&2
    echo "Set PYTHON_BIN to a matching interpreter, for example:" >&2
    echo "  PYTHON_BIN=python${required_python_minor} REQUIRED_PYTHON_MINOR=${required_python_minor} VENV_DIR=.venv-py${required_python_minor} ./run.sh" >&2
    exit 1
  fi
fi

if [[ ! -x "${venv_python}" ]]; then
  echo "Creating Python virtual environment in ${venv_dir}"
  "${python_bin}" -m venv "${venv_dir}"
fi

if [[ -n "${required_python_minor}" ]]; then
  venv_python_minor="$("${venv_python}" - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
  if [[ "${venv_python_minor}" != "${required_python_minor}" ]]; then
    echo "${venv_dir} uses Python ${venv_python_minor}, but Python ${required_python_minor} is required." >&2
    echo "Use a different VENV_DIR or recreate the environment with the matching interpreter." >&2
    exit 1
  fi
fi

if [[ ! -f "${requirements_file}" ]]; then
  echo "Missing ${requirements_file}" >&2
  exit 1
fi

setup_needed=0
if [[ ! -f "${deps_stamp}" || "${requirements_file}" -nt "${deps_stamp}" ]]; then
  setup_needed=1
elif ! "${venv_python}" - <<'PY'
import importlib.util
import sys

required_modules = {
    "numpy": "numpy",
    "opencv-python": "cv2",
    "tensorflow": "tensorflow",
    "python-can": "can",
}
optional_runtime_modules = {
    "tflite-runtime": "tflite_runtime",
    "onnxruntime": "onnxruntime",
}
missing = [package for package, module in required_modules.items() if importlib.util.find_spec(module) is None]
if missing:
    print("Missing Python packages:", ", ".join(missing))
    sys.exit(1)
runtime_missing = [
    package
    for package, module in optional_runtime_modules.items()
    if importlib.util.find_spec(module) is None
]
if runtime_missing:
    print("Optional runtime packages not installed:", ", ".join(runtime_missing))
PY
then
  setup_needed=1
fi

if [[ "${setup_needed}" == "1" ]]; then
  echo "Installing Python dependencies from ${requirements_file}"
  "${venv_python}" -m pip install --upgrade pip
  "${venv_python}" -m pip install -r "${requirements_file}"
  touch "${deps_stamp}"
fi

"${venv_python}" - <<'PY'
import importlib.metadata
import importlib.util

packages = ["numpy", "opencv-python", "tensorflow", "tflite-runtime", "python-can", "onnxruntime", "rknn-toolkit-lite2"]
versions = []
for package in packages:
    try:
        versions.append(f"{package}=={importlib.metadata.version(package)}")
    except importlib.metadata.PackageNotFoundError:
        versions.append(f"{package}=missing")

if importlib.util.find_spec("tflite_runtime") is not None:
    model_runtime = "tflite-runtime"
else:
    model_runtime = "tensorflow SavedModel fallback"

if importlib.util.find_spec("rknnlite") is not None:
    segmentation_runtime = "rknn-toolkit-lite2"
elif importlib.util.find_spec("onnxruntime") is not None:
    segmentation_runtime = "onnxruntime"
else:
    segmentation_runtime = "transformers/torch fallback if installed"

print("Python deps:", ", ".join(versions))
print("Texture model runtime:", model_runtime)
print("Segmentation runtime:", segmentation_runtime)
PY

ensure_rknn_runtime

if [ "$(hostname)" = "orangepi5pro" ]; then
  echo "detected orangepi"
  if ip link show can0 > /dev/null 2>&1; then
    if ip link show can0 | grep -q "state DOWN"; then
      ip link set can0 up type can bitrate 1000000 || sudo ip link set can0 up type can bitrate 1000000
    fi
  fi
fi

exec "${venv_python}" server.py --host 0.0.0.0 --port 8090
