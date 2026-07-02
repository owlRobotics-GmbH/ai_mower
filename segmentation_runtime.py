from __future__ import annotations

import importlib.util
import json
import os
import platform
import threading
import time
from pathlib import Path

import cv2
import numpy as np


DEFAULT_SEGMENTATION_MODEL_ID = os.environ.get(
    "AI_MOWER_SEGMENTATION_MODEL_ID",
    "nvidia/segformer-b0-finetuned-ade-512-512",
)
DEFAULT_SEGMENTATION_RKNN = Path(os.environ.get("AI_MOWER_SEGMENTATION_RKNN", "data/segmentation/model.rknn"))
DEFAULT_SEGMENTATION_ONNX = Path(os.environ.get("AI_MOWER_SEGMENTATION_ONNX", "data/segmentation/model.onnx"))
DEFAULT_SEGMENTATION_LABELS = Path(os.environ.get("AI_MOWER_SEGMENTATION_LABELS", "data/segmentation/labels.json"))
DEFAULT_SEGMENTATION_BACKEND = os.environ.get("AI_MOWER_SEGMENTATION_BACKEND", "auto").lower()

GARDEN_COLORS = {
    "grass": (60, 170, 80),
    "plant": (35, 130, 70),
    "tree": (25, 100, 55),
    "earth": (135, 95, 55),
    "path": (180, 160, 120),
    "sky": (90, 170, 230),
    "road": (90, 90, 90),
    "wall": (160, 150, 140),
    "fence": (145, 115, 85),
    "flower": (210, 80, 170),
    "field": (95, 150, 70),
}


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve() if not path.is_absolute() else path.expanduser()


def _load_labels(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {idx: str(label) for idx, label in enumerate(data)}
    if isinstance(data, dict):
        labels = data.get("id2label", data)
        return {int(idx): str(label) for idx, label in labels.items()}
    return {}


def _default_palette(count: int, labels: dict[int, str]) -> np.ndarray:
    rng = np.random.default_rng(20240525)
    palette = rng.integers(40, 236, size=(max(1, count), 3), dtype=np.uint8)
    for idx, label in labels.items():
        color = GARDEN_COLORS.get(str(label).lower())
        if color and 0 <= idx < len(palette):
            palette[idx] = color
    return palette


def _is_rk3588_platform() -> bool:
    if platform.machine().lower() != "aarch64":
        return False
    try:
        compatible = Path("/proc/device-tree/compatible").read_bytes().decode("latin1").lower()
    except Exception:
        compatible = ""
    return "rk3588" in compatible or "orangepi" in platform.node().lower()


class SegmentationRuntime:
    def __init__(
        self,
        *,
        rknn_path: Path = DEFAULT_SEGMENTATION_RKNN,
        onnx_path: Path = DEFAULT_SEGMENTATION_ONNX,
        labels_path: Path = DEFAULT_SEGMENTATION_LABELS,
        input_size: int | None = None,
    ):
        self.rknn_path = _resolve(Path(rknn_path))
        self.onnx_path = _resolve(Path(onnx_path))
        self.labels_path = _resolve(Path(labels_path))
        self.input_size = int(input_size or os.environ.get("AI_MOWER_SEGMENTATION_INPUT_SIZE", "512"))
        self.alpha = float(os.environ.get("AI_MOWER_SEGMENTATION_ALPHA", "0.48"))
        self.rknn_input = os.environ.get("AI_MOWER_SEGMENTATION_RKNN_INPUT", "nhwc_uint8").lower()
        self.requested_backend = DEFAULT_SEGMENTATION_BACKEND
        self.lock = threading.Lock()
        self.backend = "none"
        self.model = None
        self.session = None
        self.processor = None
        self.torch = None
        self.input_name = ""
        self.output_name = ""
        self.labels = _load_labels(self.labels_path)
        self.palette = _default_palette(max(self.labels.keys(), default=0) + 1, self.labels)
        self.last_error = ""
        self.last_ms = 0.0
        self.last_loaded_at = 0.0

    def available(self) -> bool:
        return (
            self.model is not None
            or self.session is not None
            or self.rknn_path.exists()
            or self.onnx_path.exists()
            or importlib.util.find_spec("transformers") is not None
        )

    def snapshot(self) -> dict:
        return {
            "available": self.available(),
            "loaded": self.backend != "none",
            "backend": self.backend,
            "rknn_path": str(self.rknn_path),
            "onnx_path": str(self.onnx_path),
            "labels_path": str(self.labels_path),
            "input_size": self.input_size,
            "requested_backend": self.requested_backend,
            "last_error": self.last_error,
            "last_ms": self.last_ms,
            "last_loaded_at": self.last_loaded_at,
        }

    def load(self) -> None:
        if self.backend != "none":
            return
        if self.requested_backend == "rknn":
            self._load_rknn()
            return
        if self.requested_backend == "onnx":
            self._load_onnx()
            return
        if self.requested_backend == "transformers":
            self._load_transformers()
            return
        if self.requested_backend != "auto":
            raise RuntimeError(f"Unsupported segmentation backend: {self.requested_backend}")

        if _is_rk3588_platform() and self.rknn_path.exists():
            try:
                self._load_rknn()
                return
            except Exception as exc:
                if not self.onnx_path.exists():
                    raise
                self.last_error = f"RKNN unavailable, using ONNX: {exc}"

        if self.onnx_path.exists():
            self._load_onnx()
            return
        if self.rknn_path.exists() and importlib.util.find_spec("rknnlite") is not None:
            self._load_rknn()
            return
        self._load_transformers()

    def _load_rknn(self) -> None:
        try:
            from rknnlite.api import RKNNLite
        except Exception as exc:
            raise RuntimeError("RKNN model found, but rknnlite is not installed") from exc
        model = RKNNLite()
        ret = model.load_rknn(str(self.rknn_path))
        if ret != 0:
            raise RuntimeError(f"Could not load RKNN model: {self.rknn_path}")
        core_mask = int(os.environ.get("AI_MOWER_SEGMENTATION_RKNN_CORE_MASK", "0"))
        ret = model.init_runtime(core_mask=core_mask)
        if ret != 0:
            raise RuntimeError("Could not initialize RKNN runtime")
        self.model = model
        self.backend = "rknn"
        self.last_loaded_at = time.time()

    def _load_onnx(self) -> None:
        try:
            import onnxruntime as ort
        except Exception as exc:
            raise RuntimeError("ONNX model found, but onnxruntime is not installed") from exc
        providers = ["CPUExecutionProvider"]
        self.session = ort.InferenceSession(str(self.onnx_path), providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        self.backend = "onnx"
        self.last_loaded_at = time.time()

    def _load_transformers(self) -> None:
        try:
            import torch
            from transformers import AutoImageProcessor, SegformerForSemanticSegmentation
        except Exception as exc:
            raise RuntimeError(
                "No segmentation RKNN/ONNX model found and transformers/torch are not installed"
            ) from exc
        threads = int(os.environ.get("AI_MOWER_SEGMENTATION_TORCH_THREADS", "2"))
        if threads > 0:
            torch.set_num_threads(threads)
            torch.set_num_interop_threads(max(1, min(threads, 2)))
        model_id = DEFAULT_SEGMENTATION_MODEL_ID
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = SegformerForSemanticSegmentation.from_pretrained(model_id).eval()
        self.labels = {int(idx): label for idx, label in self.model.config.id2label.items()}
        self.palette = _default_palette(max(self.labels.keys(), default=0) + 1, self.labels)
        self.torch = torch
        self.backend = "transformers"
        self.last_loaded_at = time.time()

    def preprocess_nchw_float(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        rgb = rgb.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        rgb = (rgb - mean) / std
        return np.expand_dims(rgb.transpose(2, 0, 1), axis=0).astype(np.float32)

    def preprocess_rknn(self, frame: np.ndarray) -> np.ndarray:
        if self.rknn_input == "nchw_float":
            return self.preprocess_nchw_float(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        return np.expand_dims(rgb, axis=0).astype(np.uint8)

    def render(self, frame: np.ndarray) -> np.ndarray:
        if not self.lock.acquire(blocking=False):
            return self.error_frame(frame, "Segmentation busy")
        try:
            self.load()
            started = time.time()
            segmentation = self.segment(frame)
            output = self.overlay(frame, segmentation)
            self.last_ms = (time.time() - started) * 1000.0
            self.last_error = ""
            return output
        except Exception as exc:
            self.last_error = str(exc)
            return self.error_frame(frame, str(exc))
        finally:
            self.lock.release()

    def segment(self, frame: np.ndarray) -> np.ndarray:
        if self.backend == "rknn":
            outputs = self.model.inference(inputs=[self.preprocess_rknn(frame)])
            return self.decode_output(outputs[0], frame.shape[:2])
        if self.backend == "onnx":
            output = self.session.run([self.output_name], {self.input_name: self.preprocess_nchw_float(frame)})[0]
            return self.decode_output(output, frame.shape[:2])
        if self.backend == "transformers":
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = cv2.resize(rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
            inputs = self.processor(images=image, return_tensors="pt")
            with self.torch.inference_mode():
                outputs = self.model(**inputs)
                logits = self.torch.nn.functional.interpolate(
                    outputs.logits,
                    size=frame.shape[:2],
                    mode="bilinear",
                    align_corners=False,
                )
                return logits.argmax(dim=1)[0].cpu().numpy().astype(np.int64)
        raise RuntimeError("Segmentation model is not loaded")

    def decode_output(self, output: np.ndarray, target_hw: tuple[int, int]) -> np.ndarray:
        arr = np.asarray(output)
        if arr.ndim == 4:
            arr = arr[0]
        if arr.ndim == 3:
            label_count = len(self.labels)
            if label_count and arr.shape[0] == label_count:
                arr = np.argmax(arr, axis=0)
            elif label_count and arr.shape[-1] == label_count:
                arr = np.argmax(arr, axis=-1)
            elif arr.shape[0] > 4:
                arr = np.argmax(arr, axis=0)
            else:
                arr = np.argmax(arr, axis=-1)
        if arr.ndim != 2:
            raise RuntimeError(f"Unsupported segmentation output shape: {np.asarray(output).shape}")
        return cv2.resize(arr.astype(np.int32), (target_hw[1], target_hw[0]), interpolation=cv2.INTER_NEAREST)

    def overlay(self, frame: np.ndarray, segmentation: np.ndarray) -> np.ndarray:
        max_label = int(np.max(segmentation)) if segmentation.size else 0
        if max_label >= len(self.palette):
            self.palette = _default_palette(max_label + 1, self.labels)
        mask_rgb = self.palette[segmentation.clip(0, len(self.palette) - 1)]
        mask_bgr = cv2.cvtColor(mask_rgb, cv2.COLOR_RGB2BGR)
        blended = cv2.addWeighted(frame, 1.0 - self.alpha, mask_bgr, self.alpha, 0)
        self.draw_legend(blended, segmentation)
        return blended

    def draw_legend(self, frame: np.ndarray, segmentation: np.ndarray) -> None:
        labels, counts = np.unique(segmentation, return_counts=True)
        order = np.argsort(counts)[::-1][:5]
        rows = []
        total = max(1, int(segmentation.size))
        for idx in order:
            label_id = int(labels[idx])
            label = self.labels.get(label_id, str(label_id))
            pct = 100.0 * float(counts[idx]) / total
            rows.append((label_id, label, pct))
        if not rows:
            return
        width = min(frame.shape[1] - 20, 360)
        height = 30 + 24 * len(rows)
        cv2.rectangle(frame, (10, 10), (10 + width, 10 + height), (22, 26, 31), -1)
        cv2.putText(frame, f"seg {self.backend} {self.last_ms:.0f} ms", (22, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (245, 248, 252), 1, cv2.LINE_AA)
        for row, (label_id, label, pct) in enumerate(rows):
            y = 60 + row * 24
            color = tuple(int(v) for v in self.palette[label_id % len(self.palette)][::-1])
            cv2.rectangle(frame, (22, y - 14), (38, y + 2), color, -1)
            cv2.putText(frame, f"{label[:24]} {pct:.1f}%", (48, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (245, 248, 252), 1, cv2.LINE_AA)

    @staticmethod
    def error_frame(frame: np.ndarray, message: str) -> np.ndarray:
        output = frame.copy()
        cv2.rectangle(output, (0, 0), (output.shape[1], min(96, output.shape[0])), (24, 24, 24), -1)
        cv2.putText(output, "Segmentation unavailable", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(output, message[:110], (16, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1, cv2.LINE_AA)
        return output
