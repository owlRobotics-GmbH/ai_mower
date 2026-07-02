from __future__ import annotations

import importlib.util
import multiprocessing
import os
import queue
import sys
import threading
import time
import types
from pathlib import Path

import cv2
import numpy as np


DEFAULT_FAST_DEPTH_ROOT = Path(os.environ.get("AI_MOWER_FASTDEPTH_ROOT", "~/dev/FastDepth_Hagaik92")).expanduser()
DEFAULT_FAST_DEPTH_CHECKPOINT = os.environ.get(
    "AI_MOWER_FASTDEPTH_CHECKPOINT",
    str(DEFAULT_FAST_DEPTH_ROOT / "Weights" / "FastDepthV2_L1_Best.pth"),
)


def _infer_backbone(path: Path) -> str:
    return "mobilenetv2" if "v2" in path.name.lower() else "mobilenet"


def _ensure_optional_torchvision_stub() -> None:
    if importlib.util.find_spec("torchvision") is not None:
        return
    torchvision = types.ModuleType("torchvision")
    torchvision.models = types.ModuleType("torchvision.models")
    torchvision.transforms = types.ModuleType("torchvision.transforms")
    torchvision.transforms.functional = types.ModuleType("torchvision.transforms.functional")
    sys.modules.setdefault("torchvision", torchvision)
    sys.modules.setdefault("torchvision.models", torchvision.models)
    sys.modules.setdefault("torchvision.transforms", torchvision.transforms)
    sys.modules.setdefault("torchvision.transforms.functional", torchvision.transforms.functional)


class FastDepthRuntime:
    def __init__(
        self,
        *,
        root: Path = DEFAULT_FAST_DEPTH_ROOT,
        checkpoint: str | Path = DEFAULT_FAST_DEPTH_CHECKPOINT,
        input_size: int | None = None,
        use_worker: bool | None = None,
    ):
        self.root = Path(root).expanduser()
        self.checkpoint = Path(checkpoint).expanduser()
        self.input_size = int(input_size or os.environ.get("AI_MOWER_FASTDEPTH_INPUT_SIZE", "224"))
        self.backbone = os.environ.get("AI_MOWER_FASTDEPTH_BACKBONE") or _infer_backbone(self.checkpoint)
        self.use_worker = (
            os.environ.get("AI_MOWER_FASTDEPTH_PROCESS", "1").lower() not in {"0", "false", "no", "off"}
            if use_worker is None
            else bool(use_worker)
        )
        self.lock = threading.Lock()
        self.model = None
        self.torch = None
        self.last_error = ""
        self.last_ms = 0.0
        self.last_loaded_at = 0.0
        self.request_id = 0
        self.worker = None
        self.worker_requests = None
        self.worker_responses = None
        self.worker_context = None

    def available(self) -> bool:
        return self.model is not None or (self.root.exists() and self.checkpoint.exists())

    def snapshot(self) -> dict:
        return {
            "available": self.available(),
            "loaded": self.model is not None,
            "root": str(self.root),
            "checkpoint": str(self.checkpoint),
            "backbone": self.backbone,
            "input_size": self.input_size,
            "process": self.use_worker,
            "worker_alive": bool(self.worker and self.worker.is_alive()),
            "last_error": self.last_error,
            "last_ms": self.last_ms,
            "last_loaded_at": self.last_loaded_at,
        }

    def load(self) -> None:
        if self.model is not None:
            return
        if not self.root.exists():
            raise RuntimeError(f"FastDepth repo not found: {self.root}")
        if not self.checkpoint.exists():
            raise RuntimeError(f"FastDepth checkpoint not found: {self.checkpoint}")
        try:
            import torch
        except Exception as exc:
            raise RuntimeError("FastDepth needs PyTorch. Install torch for depth view.") from exc

        _ensure_optional_torchvision_stub()
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        try:
            from models import FastDepth, FastDepthV2
        except Exception as exc:
            raise RuntimeError(f"Could not import FastDepth models from {self.root}: {exc}") from exc

        if self.backbone == "mobilenet":
            model = FastDepth()
        elif self.backbone == "mobilenetv2":
            model = FastDepthV2()
        else:
            raise RuntimeError(f"Unsupported FastDepth backbone: {self.backbone}")

        threads = int(os.environ.get("AI_MOWER_FASTDEPTH_THREADS", "2"))
        if threads > 0:
            torch.set_num_threads(threads)
            torch.set_num_interop_threads(max(1, min(threads, 2)))
        checkpoint = torch.load(self.checkpoint, map_location="cpu", weights_only=False)
        state_dict = checkpoint["model_state_dict"] if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint else checkpoint
        model.load_state_dict(state_dict)
        model.eval()
        torch.set_grad_enabled(False)
        self.torch = torch
        self.model = model
        self.last_loaded_at = time.time()
        self.last_error = ""

    def render(self, frame: np.ndarray) -> np.ndarray:
        with self.lock:
            if self.use_worker:
                return self.render_with_worker(frame)
            return self.render_in_process(frame)

    def render_in_process(self, frame: np.ndarray) -> np.ndarray:
        try:
            self.load()
            started = time.time()
            input_frame = cv2.resize(frame, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
            input_frame = cv2.cvtColor(input_frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            tensor = self.torch.from_numpy(input_frame.transpose(2, 0, 1)).unsqueeze(0)
            with self.torch.no_grad():
                prediction = self.model(tensor)
            depth = prediction.squeeze().detach().cpu().numpy().astype(np.float32)
            color = self.colorize_depth(depth)
            color = cv2.resize(color, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
            self.last_ms = (time.time() - started) * 1000.0
            self.last_error = ""
            return color
        except Exception as exc:
            self.last_error = str(exc)
            return self.error_frame(frame, str(exc))

    def render_with_worker(self, frame: np.ndarray) -> np.ndarray:
        try:
            self.ensure_worker()
            self.request_id += 1
            request_id = self.request_id
            while True:
                try:
                    self.worker_responses.get_nowait()
                except queue.Empty:
                    break
            self.worker_requests.put((request_id, frame), timeout=0.2)
            timeout = float(os.environ.get("AI_MOWER_FASTDEPTH_TIMEOUT", "5.0"))
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self.worker is not None and not self.worker.is_alive():
                    raise RuntimeError(f"FastDepth worker exited with code {self.worker.exitcode}")
                try:
                    response_id, ok, payload, elapsed_ms = self.worker_responses.get(timeout=0.1)
                except queue.Empty:
                    continue
                if response_id != request_id:
                    continue
                self.last_ms = float(elapsed_ms or 0.0)
                if ok:
                    self.last_error = ""
                    self.last_loaded_at = self.last_loaded_at or time.time()
                    return payload
                self.last_error = str(payload)
                return self.error_frame(frame, self.last_error)
            raise RuntimeError("FastDepth worker timed out")
        except Exception as exc:
            self.stop_worker()
            self.last_error = str(exc)
            return self.error_frame(frame, str(exc))

    def ensure_worker(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        self.stop_worker()
        start_method = os.environ.get("AI_MOWER_FASTDEPTH_START_METHOD", "spawn")
        if start_method not in multiprocessing.get_all_start_methods():
            start_method = multiprocessing.get_start_method()
        self.worker_context = multiprocessing.get_context(start_method)
        self.worker_requests = self.worker_context.Queue(maxsize=1)
        self.worker_responses = self.worker_context.Queue(maxsize=1)
        config = {
            "root": str(self.root),
            "checkpoint": str(self.checkpoint),
            "input_size": self.input_size,
            "backbone": self.backbone,
        }
        self.worker = self.worker_context.Process(
            target=_worker_main,
            args=(self.worker_requests, self.worker_responses, config),
            name="AIMowerFastDepth",
            daemon=True,
        )
        self.worker.start()

    def stop_worker(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None and worker.is_alive():
            try:
                worker.terminate()
                worker.join(timeout=1.0)
            except Exception:
                pass

    @staticmethod
    def colorize_depth(depth: np.ndarray) -> np.ndarray:
        d_min = float(np.nanmin(depth))
        d_max = float(np.nanmax(depth))
        if not np.isfinite(d_min) or not np.isfinite(d_max) or d_max <= d_min:
            normalized = np.zeros(depth.shape, dtype=np.uint8)
        else:
            normalized = ((depth - d_min) / (d_max - d_min) * 255.0).clip(0, 255).astype(np.uint8)
        return cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)

    @staticmethod
    def error_frame(frame: np.ndarray, message: str) -> np.ndarray:
        output = frame.copy()
        cv2.rectangle(output, (0, 0), (output.shape[1], min(90, output.shape[0])), (24, 24, 24), -1)
        cv2.putText(output, "FastDepth unavailable", (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(output, message[:100], (16, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1, cv2.LINE_AA)
        return output


def _worker_main(requests, responses, config: dict) -> None:
    runtime = FastDepthRuntime(
        root=Path(config["root"]),
        checkpoint=Path(config["checkpoint"]),
        input_size=int(config["input_size"]),
        use_worker=False,
    )
    runtime.backbone = str(config.get("backbone") or runtime.backbone)
    while True:
        request_id, frame = requests.get()
        started = time.time()
        output = runtime.render_in_process(frame)
        elapsed_ms = (time.time() - started) * 1000.0
        if runtime.last_error:
            responses.put((request_id, False, runtime.last_error, elapsed_ms))
        else:
            responses.put((request_id, True, output, elapsed_ms))
