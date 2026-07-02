from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2

from model_runtime import crop_frame


DEFAULT_CAMERA_RESOLUTION = os.environ.get("AI_MOWER_CAMERA_RESOLUTION", "1280x720")
CAMERA_DEBUG = os.environ.get("AI_MOWER_CAMERA_DEBUG", "1").lower() not in {"0", "false", "no", "off"}
LAST_CANDIDATE_DEBUG = {"key": None, "time": 0.0}
CONTROL_RE = re.compile(r"^\s*(?P<name>[a-zA-Z0-9_]+)\s+0x[0-9a-fA-F]+\s+\((?P<type>[^)]+)\)\s+:\s+(?P<rest>.*)$")
DISCRETE_SIZE_RE = re.compile(r"\bSize:\s+Discrete\s+(?P<width>\d+)x(?P<height>\d+)")
STEPWISE_SIZE_RE = re.compile(
    r"\bSize:\s+Stepwise\s+(?P<min_width>\d+)x(?P<min_height>\d+)\s+-\s+"
    r"(?P<max_width>\d+)x(?P<max_height>\d+)"
)


def camera_debug(message: str) -> None:
    if CAMERA_DEBUG:
        print(f"[camera-debug {time.strftime('%H:%M:%S')}] {message}", flush=True)


def fourcc_text(value: float) -> str:
    code = int(value or 0)
    chars = []
    for shift in [0, 8, 16, 24]:
        ch = (code >> shift) & 0xFF
        chars.append(chr(ch) if 32 <= ch <= 126 else ".")
    return "".join(chars)


def _parse_camera_index_strict(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid camera index: {value}") from exc


def video_device_index(path: Path) -> int | None:
    name = path.resolve().name if path.exists() else path.name
    if name.startswith("video") and name[5:].isdigit():
        return int(name[5:])
    return None


def v4l2_device_info(index: int) -> str | None:
    tool = shutil.which("v4l2-ctl")
    if tool is None:
        return None
    try:
        result = subprocess.run(
            [tool, f"--device=/dev/video{index}", "--all"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def run_v4l2(index: int, *args: str) -> subprocess.CompletedProcess | None:
    tool = shutil.which("v4l2-ctl")
    if tool is None:
        return None
    try:
        return subprocess.run(
            [tool, f"--device=/dev/video{index}", *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def parse_control_line(line: str) -> dict | None:
    match = CONTROL_RE.match(line)
    if not match:
        return None
    control = {"name": match.group("name"), "type": match.group("type")}
    for key in ["min", "max", "step", "default", "value"]:
        value_match = re.search(rf"\b{key}=(-?\d+)", match.group("rest"))
        if value_match:
            control[key] = int(value_match.group(1))
    flags_match = re.search(r"\bflags=([a-zA-Z0-9_,]+)", match.group("rest"))
    control["flags"] = flags_match.group(1).split(",") if flags_match else []
    label_match = re.search(r"\(([^)]+)\)\s*$", match.group("rest"))
    if label_match:
        control["label"] = label_match.group(1)
    return control


def cv2_open_camera(index: int):
    attempts = [
        (index, cv2.CAP_V4L2, f"index {index} CAP_V4L2"),
    ]
    for target, backend, label in attempts:
        camera_debug(f"OpenCV open attempt: {label}")
        cap = cv2.VideoCapture(target, backend)
        if cap.isOpened():
            camera_debug(f"OpenCV open ok: {label}")
            return cap
        camera_debug(f"OpenCV open failed: {label}")
        cap.release()
    camera_debug(f"OpenCV all open attempts failed for /dev/video{index}")
    return cv2.VideoCapture()


def list_camera_controls(index: int) -> dict[str, dict]:
    result = run_v4l2(index, "--list-ctrls")
    if result is None or result.returncode != 0:
        return {}
    controls = {}
    for line in result.stdout.splitlines():
        control = parse_control_line(line)
        if control:
            controls[control["name"]] = control
    return controls


def list_camera_resolutions(index: int) -> dict:
    result = run_v4l2(index, "--list-formats-ext")
    if result is None:
        return {
            "available": False,
            "resolutions": [],
            "error": "v4l2-ctl not found",
        }
    if result.returncode != 0:
        return {
            "available": False,
            "resolutions": [],
            "error": result.stdout.strip() or "Could not list camera resolutions",
        }

    resolutions: dict[tuple[int, int], dict] = {}
    ranges = []
    for line in result.stdout.splitlines():
        discrete = DISCRETE_SIZE_RE.search(line)
        if discrete:
            width = int(discrete.group("width"))
            height = int(discrete.group("height"))
            resolutions[(width, height)] = {
                "value": f"{width}x{height}",
                "width": width,
                "height": height,
                "label": f"{width} x {height}",
            }
            continue

        stepwise = STEPWISE_SIZE_RE.search(line)
        if stepwise:
            min_width = int(stepwise.group("min_width"))
            min_height = int(stepwise.group("min_height"))
            max_width = int(stepwise.group("max_width"))
            max_height = int(stepwise.group("max_height"))
            ranges.append({
                "min": {"width": min_width, "height": min_height, "value": f"{min_width}x{min_height}"},
                "max": {"width": max_width, "height": max_height, "value": f"{max_width}x{max_height}"},
            })

    ordered = sorted(resolutions.values(), key=lambda item: (item["width"] * item["height"], item["width"], item["height"]))
    return {
        "available": bool(ordered or ranges),
        "resolutions": ordered,
        "ranges": ranges,
        "error": "" if ordered or ranges else "No V4L2 resolutions found",
    }


def set_camera_control(index: int, name: str, value: int) -> None:
    result = run_v4l2(index, "-c", f"{name}={int(value)}")
    if result is None:
        raise RuntimeError("v4l2-ctl not found")
    if result.returncode != 0:
        raise RuntimeError(result.stdout.strip() or f"Could not set camera control {name}")


def camera_exposure_controls(index: int) -> dict:
    controls = list_camera_controls(index)
    auto = controls.get("auto_exposure") or controls.get("exposure_auto")
    exposure = controls.get("exposure_time_absolute")
    dynamic = controls.get("exposure_dynamic_framerate")
    auto_value = auto.get("value") if auto else None
    return {
        "available": bool(auto or exposure),
        "auto_control": auto,
        "exposure_control": exposure,
        "dynamic_framerate_control": dynamic,
        "auto_enabled": None if auto_value is None else auto_value not in {0, 1},
        "dynamic_framerate_enabled": None if dynamic is None else bool(dynamic.get("value", 0)),
        "error": "" if controls else "No V4L2 controls found",
    }


def set_exposure_controls(index: int, *, auto_exposure=None, exposure_time=None, dynamic_framerate=None) -> dict:
    controls = list_camera_controls(index)
    auto = controls.get("auto_exposure") or controls.get("exposure_auto")
    exposure = controls.get("exposure_time_absolute")
    dynamic = controls.get("exposure_dynamic_framerate")
    if auto_exposure is not None and auto:
        set_camera_control(index, auto["name"], 3 if bool(auto_exposure) else 1)
    if dynamic_framerate is not None and dynamic:
        set_camera_control(index, dynamic["name"], 1 if bool(dynamic_framerate) else 0)
    if exposure_time is not None and exposure and not bool(auto_exposure):
        value = int(exposure_time)
        value = max(int(exposure.get("min", value)), min(int(exposure.get("max", value)), value))
        if auto_exposure is None and auto and int(auto.get("value", 3)) not in {0, 1}:
            set_camera_control(index, auto["name"], 1)
        set_camera_control(index, exposure["name"], value)
    return camera_exposure_controls(index)


def device_caps(info: str) -> str:
    marker = "Device Caps      :"
    if marker not in info:
        return info
    caps = info.split(marker, 1)[1]
    for end_marker in ["Media Driver Info:", "Interface Info:", "Priority:"]:
        if end_marker in caps:
            caps = caps.split(end_marker, 1)[0]
            break
    return caps


def supports_video_capture(index: int) -> bool:
    info = v4l2_device_info(index)
    if info is None:
        supported = shutil.which("v4l2-ctl") is None
        camera_debug(f"/dev/video{index}: no v4l2 info, supported={supported}")
        return supported
    caps = device_caps(info)
    supported = "Video Capture" in caps
    card = ""
    driver = ""
    for line in info.splitlines():
        if "Card type" in line:
            card = line.split(":", 1)[1].strip()
        elif "Driver name" in line and not driver:
            driver = line.split(":", 1)[1].strip()
    camera_debug(f"/dev/video{index}: driver={driver or '?'} card={card or '?'} video_capture={supported}")
    return supported


def camera_priority(index: int) -> tuple[int, int]:
    info = v4l2_device_info(index)
    if info is None:
        return (3, index)
    if "Driver name      : uvcvideo" in info:
        return (0, index)
    if "Video Capture Multiplanar" not in device_caps(info):
        return (1, index)
    return (2, index)


def candidate_camera_indices() -> list[int]:
    env_camera = os.environ.get("AI_MOWER_CAMERA")
    if env_camera and env_camera.lower() != "auto":
        try:
            forced = _parse_camera_index_strict(env_camera)
            camera_debug(f"Camera candidates forced by AI_MOWER_CAMERA={env_camera}: [{forced}]")
            return [forced]
        except ValueError:
            camera_debug(f"Camera candidates forced by AI_MOWER_CAMERA={env_camera}: invalid")
            return []

    candidates = []
    probed_paths = []
    for path in [Path("/dev/video-camera0"), *sorted(Path("/dev").glob("video[0-9]*"))]:
        index = video_device_index(path)
        probed_paths.append(f"{path}->{index}")
        if index is not None and supports_video_capture(index):
            candidates.append(index)

    seen = set()
    unique = [idx for idx in candidates if not (idx in seen or seen.add(idx))]
    ordered = sorted(unique, key=camera_priority)
    debug_key = (tuple(probed_paths), tuple(ordered))
    now = time.time()
    if debug_key != LAST_CANDIDATE_DEBUG["key"] or now - LAST_CANDIDATE_DEBUG["time"] > 30.0:
        LAST_CANDIDATE_DEBUG["key"] = debug_key
        LAST_CANDIDATE_DEBUG["time"] = now
        camera_debug(f"Camera probed paths: {', '.join(probed_paths)}")
        camera_debug(f"Camera candidates sorted: {ordered}")
    return ordered


def parse_camera_index(value=None) -> int:
    try:
        parsed = _parse_camera_index_strict(value if value is not None else os.environ.get("AI_MOWER_CAMERA", "0"))
        camera_debug(f"Camera index parsed from {value!r}: {parsed}")
        return parsed
    except ValueError:
        candidates = candidate_camera_indices()
        selected = candidates[0] if candidates else 0
        camera_debug(f"Camera index auto-selected from {value!r}: {selected}")
        return selected


DEFAULT_CAMERA_INDEX = os.environ.get("AI_MOWER_CAMERA", "auto")


def open_camera(camera: str):
    candidates = candidate_camera_indices() if str(camera).lower() == "auto" else [_parse_camera_index_strict(camera)]
    camera_debug(f"open_camera request={camera!r} candidates={candidates}")
    failures = []
    for index in candidates:
        cap = cv2_open_camera(index)
        if not cap.isOpened():
            failures.append(f"{index}: open failed")
            cap.release()
            continue
        ok = False
        for _ in range(3):
            ok, frame = cap.read()
            camera_debug(f"open_camera initial read /dev/video{index}: ok={ok} shape={None if frame is None else frame.shape}")
            if ok and frame is not None:
                break
            time.sleep(0.05)
        if ok and frame is not None:
            return cap, index
        failures.append(f"{index}: frame read failed")
        cap.release()
    detail = "; ".join(failures) if failures else "no /dev/video* candidates found"
    raise RuntimeError(f"Cannot open camera {camera}: {detail}")


def parse_camera_resolution(value=None) -> tuple[int, int]:
    raw = str(value or DEFAULT_CAMERA_RESOLUTION).lower().strip()
    if "x" not in raw:
        raw = DEFAULT_CAMERA_RESOLUTION
    try:
        width, height = [int(part) for part in raw.split("x", 1)]
    except ValueError:
        width, height = 1280, 720
    width = max(160, min(4096, width))
    height = max(120, min(2160, height))
    parsed = (width, height)
    camera_debug(f"Camera resolution parsed from {value!r}: {parsed[0]}x{parsed[1]}")
    return parsed


class CameraManager:
    def __init__(self):
        self.lock = threading.Condition()
        self.start_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.generation = 0
        self.index = None
        self.resolution = None
        self.last_frame = None
        self.frame_id = 0
        self.last_error = ""
        self.last_read_at = 0.0
        self.fps = 0.0
        self.last_debug_error_at = 0.0
        self.last_open_failed_at = 0.0
        self.last_open_failed_key = None
        self.open_retry_interval = 3.0

    def start(self, index: int = 0, resolution: tuple[int, int] | None = None) -> None:
        resolution = resolution or parse_camera_resolution()
        request_key = (index, resolution)
        with self.start_lock:
            old_thread = None
            with self.lock:
                if self.thread and self.thread.is_alive() and self.index == index and self.resolution == resolution:
                    return
                if (
                    self.last_open_failed_key == request_key
                    and time.time() - self.last_open_failed_at < self.open_retry_interval
                ):
                    return
                if self.thread and self.thread.is_alive():
                    camera_debug(f"CameraManager.start stopping old camera index={self.index} resolution={self.resolution}")
                    self.stop_event.set()
                    old_thread = self.thread
            if old_thread:
                old_thread.join(timeout=1.5)
                camera_debug(f"CameraManager.start old thread alive after join={old_thread.is_alive()}")

            stop_event = threading.Event()
            with self.lock:
                if self.thread and self.thread.is_alive() and self.index == index and self.resolution == resolution:
                    return
                self.generation += 1
                generation = self.generation
                self.stop_event = stop_event
                self.index = index
                self.resolution = resolution
                self.last_frame = None
                self.frame_id = 0
                self.last_read_at = 0.0
                self.fps = 0.0
                self.last_error = ""
                self.last_debug_error_at = 0.0
                camera_debug(f"CameraManager.start new reader generation={generation} index={index} resolution={resolution[0]}x{resolution[1]}")
                self.thread = threading.Thread(
                    target=self._reader_loop,
                    args=(generation, index, resolution, stop_event),
                    name="AIMowerCamera",
                    daemon=True,
                )
                self.thread.start()

    def stop(self) -> None:
        with self.lock:
            camera_debug(f"CameraManager.stop index={self.index} resolution={self.resolution}")
            self.stop_event.set()
            thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
            camera_debug(f"CameraManager.stop thread alive after join={thread.is_alive()}")

    def _reader_loop(self, generation: int, index: int, resolution: tuple[int, int], stop_event: threading.Event) -> None:
        camera_debug(f"Reader loop begin generation={generation} index={index} resolution={resolution[0]}x{resolution[1]}")
        cap = cv2_open_camera(index)
        if not cap.isOpened():
            with self.lock:
                if self.generation == generation:
                    self.last_error = f"Cannot open camera {index}"
                    self.last_open_failed_at = time.time()
                    self.last_open_failed_key = (index, resolution)
                    self.lock.notify_all()
            camera_debug(f"Reader loop cannot open generation={generation} index={index}")
            cap.release()
            return
        camera_debug(f"Reader opened generation={generation} index={index}: backend={cap.getBackendName() if hasattr(cap, 'getBackendName') else '?'}")
        camera_debug(f"Reader set buffersize=1 result={cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)}")
        camera_debug(f"Reader set fourcc=MJPG result={cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))}")
        width, height = resolution
        camera_debug(f"Reader set width={width} result={cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)}")
        camera_debug(f"Reader set height={height} result={cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)}")
        camera_debug(
            "Reader reported after set: "
            f"width={cap.get(cv2.CAP_PROP_FRAME_WIDTH):.0f} "
            f"height={cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.0f} "
            f"fps={cap.get(cv2.CAP_PROP_FPS):.2f} "
            f"fourcc={fourcc_text(cap.get(cv2.CAP_PROP_FOURCC))}"
        )
        first_frame_logged = False
        try:
            while not stop_event.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    with self.lock:
                        if self.generation == generation:
                            self.last_error = "Camera frame read failed"
                            self.lock.notify_all()
                            now = time.time()
                            if now - self.last_debug_error_at > 1.0:
                                self.last_debug_error_at = now
                                camera_debug(f"Reader read failed generation={generation} index={index} ok={ok} frame_is_none={frame is None}")
                    time.sleep(0.02)
                    continue
                now = time.time()
                with self.lock:
                    if self.generation != generation:
                        break
                    if self.last_read_at:
                        instant_fps = 1.0 / max(0.001, now - self.last_read_at)
                        self.fps = instant_fps if self.fps <= 0 else (0.8 * self.fps) + (0.2 * instant_fps)
                    self.last_read_at = now
                    self.last_frame = frame
                    self.frame_id += 1
                    self.last_error = ""
                    self.lock.notify_all()
                if not first_frame_logged:
                    first_frame_logged = True
                    camera_debug(f"Reader first frame generation={generation} index={index} shape={frame.shape} frame_id={self.frame_id}")
        finally:
            camera_debug(f"Reader loop end generation={generation} index={index}")
            cap.release()

    def read(self, index: int = 0, resolution: tuple[int, int] | None = None, timeout: float = 3.0):
        latest = self.latest_frame(index, resolution, timeout=timeout)
        if latest is None:
            with self.lock:
                message = self.last_error or "Camera frame read timed out"
            camera_debug(f"CameraManager.read failed index={index} resolution={resolution}: {message}")
            raise RuntimeError(message)
        return latest["frame"]

    def latest_frame(
        self,
        index: int = 0,
        resolution: tuple[int, int] | None = None,
        *,
        after_frame_id: int | None = None,
        timeout: float = 0.0,
    ) -> dict | None:
        self.start(index, resolution)
        deadline = time.time() + timeout
        with self.lock:
            while True:
                has_frame = self.last_frame is not None
                has_new_frame = after_frame_id is None or self.frame_id > after_frame_id
                if has_frame and has_new_frame:
                    return {
                        "id": self.frame_id,
                        "frame": self.last_frame.copy(),
                        "updated": self.last_read_at,
                        "index": self.index,
                        "resolution": self.resolution,
                    }
                if self.last_error and not has_frame:
                    camera_debug(f"latest_frame returning None due to error index={index}: {self.last_error}")
                    return None
                remaining = deadline - time.time()
                if remaining <= 0:
                    camera_debug(
                        "latest_frame timeout "
                        f"index={index} resolution={resolution} has_frame={has_frame} "
                        f"frame_id={self.frame_id} after_frame_id={after_frame_id} error={self.last_error!r}"
                    )
                    return None
                self.lock.wait(timeout=remaining)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "index": self.index,
                "resolution": self.resolution,
                "fps": self.fps,
                "updated": self.last_read_at,
                "frame_id": self.frame_id,
                "error": self.last_error,
            }

    def snapshot_jpeg(self, index: int = 0, crop: dict | None = None, resolution: tuple[int, int] | None = None) -> bytes:
        frame = self.read(index, resolution)
        frame = crop_frame(frame, crop)
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise RuntimeError("Could not encode camera frame")
        return bytes(buf)
