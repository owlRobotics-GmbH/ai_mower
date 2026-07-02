from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


IMAGE_SIZE = (224, 224)
DEFAULT_LABELS = ["gras", "pavement"]
DISPLAY_LABELS = {"gras": "lawn", "pavement": "non-lawn"}
DEFAULT_CAMERA_CROP = {"enabled": True, "x": 0.25, "y": 0.5, "w": 0.5, "h": 0.5}


def normalize_crop(crop: dict | None) -> dict:
    crop = crop or {}
    enabled = bool(crop.get("enabled", False))
    x = max(0.0, min(0.95, float(crop.get("x", 0.0))))
    y = max(0.0, min(0.95, float(crop.get("y", 0.0))))
    w = max(0.05, min(1.0 - x, float(crop.get("w", 1.0))))
    h = max(0.05, min(1.0 - y, float(crop.get("h", 1.0))))
    return {"enabled": enabled, "x": x, "y": y, "w": w, "h": h}


def crop_frame(frame: np.ndarray, crop: dict | None) -> np.ndarray:
    crop = normalize_crop(crop)
    if not crop["enabled"]:
        return frame
    fh, fw = frame.shape[:2]
    x1 = int(round(crop["x"] * fw))
    y1 = int(round(crop["y"] * fh))
    x2 = int(round((crop["x"] + crop["w"]) * fw))
    y2 = int(round((crop["y"] + crop["h"]) * fh))
    x1 = max(0, min(fw - 1, x1))
    y1 = max(0, min(fh - 1, y1))
    x2 = max(x1 + 1, min(fw, x2))
    y2 = max(y1 + 1, min(fh, y2))
    return frame[y1:y2, x1:x2]


def bottom_aligned_crop(crop: dict | None) -> dict:
    crop = normalize_crop(crop)
    if crop["enabled"]:
        crop["x"] = max(0.0, (1.0 - crop["w"]) / 2.0)
        crop["y"] = max(0.0, 1.0 - crop["h"])
    return crop


def lookahead_crop(crop: dict | None) -> dict:
    crop = normalize_crop(crop)
    if crop["enabled"]:
        crop["y"] = max(0.0, crop["y"] - crop["h"])
    return crop


def softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    e = np.exp(x - np.max(x))
    total = np.sum(e)
    if total <= 0:
        return np.zeros_like(e)
    return e / total


def class_probability(probabilities: dict[str, float], label: str) -> float:
    return float(probabilities.get(label, 0.0))


def prepare_frame_bgr(frame: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, IMAGE_SIZE, interpolation=cv2.INTER_AREA)
    rgb = rgb.astype(np.float32) / 255.0
    return np.expand_dims(rgb, axis=0)


class TextureClassifier:
    def __init__(self, model_dir: Path):
        self.model_dir = Path(model_dir)
        self.labels = self._load_labels()
        self.backend = "none"
        self.interpreter: Any = None
        self.input_details: Any = None
        self.output_details: Any = None
        self.tf_model: Any = None
        self._load()

    def _load_labels(self) -> list[str]:
        path = self.model_dir / "labels.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list) and all(isinstance(x, str) for x in data):
                    return data
            except Exception:
                pass
        return list(DEFAULT_LABELS)

    def _load(self) -> None:
        tflite_path = self.model_dir / "model.tflite"
        saved_model_path = self.model_dir / "saved_model"
        if tflite_path.exists():
            try:
                import tflite_runtime.interpreter as tflite

                self.interpreter = tflite.Interpreter(str(tflite_path))
                self.interpreter.allocate_tensors()
                self.input_details = self.interpreter.get_input_details()
                self.output_details = self.interpreter.get_output_details()
                self.backend = "tflite"
                return
            except Exception:
                self.interpreter = None
        if saved_model_path.exists():
            import tensorflow as tf

            tf.config.set_visible_devices([], "GPU")
            if hasattr(tf.keras.layers, "TFSMLayer"):
                self.tf_model = tf.keras.layers.TFSMLayer(
                    str(saved_model_path),
                    call_endpoint="serve",
                )
            else:
                self.tf_model = tf.keras.models.load_model(saved_model_path)
            self.backend = "tf"

    def classify(self, frame_bgr: np.ndarray) -> dict[str, Any]:
        if self.backend == "none":
            raise RuntimeError("No trained model found")
        batch = prepare_frame_bgr(frame_bgr)
        if self.backend == "tflite":
            self.interpreter.set_tensor(self.input_details[0]["index"], batch)
            self.interpreter.invoke()
            scores = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
        else:
            outputs = self.tf_model(batch, training=False)
            if isinstance(outputs, dict):
                outputs = next(iter(outputs.values()))
            scores = outputs.numpy()[0]
        probs = softmax(scores)
        idx = int(np.argmax(probs))
        label = self.labels[idx] if idx < len(self.labels) else str(idx)
        probabilities = {
            self.labels[i] if i < len(self.labels) else str(i): float(probs[i])
            for i in range(len(probs))
        }
        return {
            "label": label,
            "score": float(probs[idx]),
            "grass_score": class_probability(probabilities, "gras"),
            "probabilities": probabilities,
            "backend": self.backend,
        }


def draw_detection_overlay(frame: np.ndarray, result: dict[str, Any]) -> np.ndarray:
    out = frame.copy()
    label = str(result.get("label", "-"))
    grass = float(result.get("grass_score", 0.0))
    probabilities = result.get("probabilities") or {}
    pavement = class_probability(probabilities, "pavement")
    h, w = out.shape[:2]
    color_for_label = lambda value: (36, 210, 80) if str(value) == "gras" else (40, 70, 230)
    color = color_for_label(label)
    crop = result.get("crop") or DEFAULT_CAMERA_CROP
    lookahead = result.get("lookahead_crop")
    lookahead_result = result.get("lookahead_result") or {}
    lookahead_color = color_for_label(lookahead_result.get("label", "-"))
    for box, box_color in ((lookahead, lookahead_color), (crop, color)):
        if not box:
            continue
        box = normalize_crop(box)
        if not box["enabled"]:
            continue
        x = int(round(box["x"] * w))
        y = int(round(box["y"] * h))
        rw = int(round(box["w"] * w))
        rh = int(round(box["h"] * h))
        cv2.rectangle(out, (x, y), (x + rw, y + rh), box_color, 3)
    lookahead_grass = float(lookahead_result.get("grass_score", 0.0))
    text = f"top lawn {lookahead_grass:.2f}  bottom lawn {grass:.2f}  non-lawn {pavement:.2f}"
    cv2.rectangle(out, (14, 14), (min(w - 14, 14 + 560), 64), (22, 26, 31), -1)
    cv2.putText(out, text, (26, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (245, 248, 252), 2)
    return out
