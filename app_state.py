from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from audio import play_robot_event_sound, play_robot_sheep_sound, play_robot_start_sound, play_robot_stop_sound, play_shutdown_sound, play_stop_button_prompt
from camera_manager import CameraManager, camera_debug, camera_exposure_controls, list_camera_resolutions, parse_camera_index, parse_camera_resolution, set_exposure_controls
from drive_bridge import DiffDrivePwmBridge
from firmware import FirmwareController
from model_runtime import DEFAULT_CAMERA_CROP, DEFAULT_LABELS, DISPLAY_LABELS, TextureClassifier, bottom_aligned_crop, crop_frame, draw_detection_overlay, lookahead_crop, normalize_crop
from trainer import train_profile
from visual_motion import VisualTurnMotionEstimator


ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT / "data"
PROFILE_ROOT = DATA_ROOT / "profiles"
SETTINGS_PATH = DATA_ROOT / "settings.json"
SESSION_LOG_PATH = DATA_ROOT / "session.log"
ALLOWED_SPLITS = {"train", "valid"}
ALLOWED_LABELS = set(DEFAULT_LABELS)
OLD_FULL_FRAME_CROP = {"enabled": False, "x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name.strip()).strip("._-")
    return slug[:64] or "profile"


def now_ms() -> int:
    return int(time.time() * 1000)


class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        self.settings = self.load_settings()
        self.session_log_path = SESSION_LOG_PATH
        self.reset_session_log_file()
        self.selected_profile = ""
        self.training = {"running": False, "profile": "", "metrics": [], "error": ""}
        self.testing = {"running": False, "profile": "", "last": None, "error": ""}
        self.joystick = {
            "x": 0.0,
            "y": 0.0,
            "left": 0.0,
            "right": 0.0,
            "active": False,
            "updated": 0.0,
            "seq": 0,
            "stale": False,
        }
        self.logs = []
        self.classifier = None
        self.classifier_profile = ""
        self.inference_thread = None
        self.inference_stop = threading.Event()
        self.inference_last_result = None
        self.inference_last_at = 0.0
        self.inference_ms = 0.0
        self.inference_last_frame_id = 0
        self.inference_debug_last_logged = 0.0
        self.inference_interval = float(os.environ.get("AI_MOWER_INFERENCE_INTERVAL", "0.35"))
        self.motion_estimator = VisualTurnMotionEstimator()
        self.camera_controls_cache = {}
        self.camera_controls_cached_at = 0.0
        self.camera_resolutions_cache = {}
        self.camera_resolutions_cached_at = 0.0
        self.camera_request_cache_key = None
        self.camera_request_cache = None
        self.system_cpu_sample = self.read_cpu_sample()
        self.hardware_stop_pressed_last = False
        self.hardware_stop_pressed_since = 0.0
        self.hardware_stop_announced_seconds = 0
        self.hardware_stop_announced_at = 0.0
        self.hardware_stop_action_valid_until = 0.0
        self.hardware_stop_action_last_at = 0.0
        self.camera = CameraManager()
        self.drive = DiffDrivePwmBridge()
        self.firmware = FirmwareController(
            camera=os.environ.get("AI_MOWER_CAMERA", "auto"),
            command_callback=self.handle_firmware_command,
            log_callback=self.add_firmware_log,
        )
        PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
        self.ensure_profile("garten")
        self.migrate_default_crops()
        profiles = self.list_profiles()
        configured_profile = str(self.settings.get("selected_profile") or "")
        if configured_profile and (PROFILE_ROOT / slugify(configured_profile)).exists():
            self.selected_profile = slugify(configured_profile)
        else:
            self.selected_profile = profiles[0]["id"]
            self.settings["selected_profile"] = self.selected_profile
            self.save_settings()
        drive_state = self.drive.set_options(**self.settings.get("drive_options", {}))
        self.settings["drive_options"] = dict(drive_state.get("options", {}))
        auto_options = self.firmware.set_auto_options(**self.settings.get("auto_options", {}))
        self.settings["auto_options"] = dict(auto_options)
        self.save_settings()
        self.firmware.start(self.selected_profile)
        self.apply_camera_controls()
        threading.Thread(target=self.hardware_stop_monitor_loop, name="HardwareStopMonitor", daemon=True).start()
        self.add_log("system", "AI mower server started")
        self.add_log(
            "robot",
            "drive options loaded: swap_sides={swap_sides} invert_left={invert_left} invert_right={invert_right} pwm_scale={pwm_scale:.2f} pwm_ramp_rate={pwm_ramp_rate:.2f} mower_pwm_ramp_rate={mower_pwm_ramp_rate:.2f}".format(**self.settings["drive_options"]),
        )
        self.restore_classification_if_enabled()

    def load_settings(self) -> dict:
        defaults = {
            "selected_profile": "",
            "camera": {"index": os.environ.get("AI_MOWER_CAMERA", "auto"), "resolution": os.environ.get("AI_MOWER_CAMERA_RESOLUTION", "1280x720")},
            "camera_controls": {},
            "drive_options": {},
            "auto_options": {},
            "classification": {"running": False, "profile": ""},
        }
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                defaults.update(loaded)
                defaults["camera"] = {**{"index": "auto", "resolution": "1280x720"}, **dict(defaults.get("camera") or {})}
                defaults["camera_controls"] = dict(defaults.get("camera_controls") or {})
                defaults["drive_options"] = dict(defaults.get("drive_options") or {})
                defaults["auto_options"] = dict(defaults.get("auto_options") or {})
                defaults["classification"] = {**{"running": False, "profile": ""}, **dict(defaults.get("classification") or {})}
        except Exception:
            pass
        return defaults

    def save_settings(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.settings, indent=2), encoding="utf-8")
        tmp.replace(SETTINGS_PATH)

    def reset_session_log_file(self) -> None:
        self.session_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_log_path.write_text("", encoding="utf-8")

    def append_session_log_file(self, entry: dict) -> None:
        try:
            with self.session_log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass

    def select_profile(self, pid: str) -> str:
        profile = self.profile_dir(pid)
        self.selected_profile = profile.name
        self.classifier = None
        self.classifier_profile = ""
        self.inference_last_result = None
        self.firmware.set_profile(profile.name)
        self.settings["selected_profile"] = profile.name
        self.save_settings()
        return profile.name

    def ensure_selected_profile_exists(self) -> None:
        if self.selected_profile and (PROFILE_ROOT / slugify(self.selected_profile)).exists():
            return
        profiles = self.list_profiles()
        if not profiles:
            profile = self.ensure_profile("garten")
            profiles = [self.read_meta(profile)]
        self.selected_profile = profiles[0]["id"]
        self.classifier = None
        self.classifier_profile = ""
        self.inference_last_result = None
        self.firmware.set_profile(self.selected_profile)
        self.settings["selected_profile"] = self.selected_profile
        self.save_settings()

    def set_camera_settings(self, camera: str | None = None, resolution: str | None = None) -> dict:
        current = dict(self.settings.get("camera") or {})
        camera_debug(f"AppState.set_camera_settings input camera={camera!r} resolution={resolution!r} current={current}")
        if camera is not None:
            current["index"] = str(camera)
        if resolution is not None:
            current["resolution"] = str(resolution)
        current.setdefault("index", "auto")
        current.setdefault("resolution", "1280x720")
        self.settings["camera"] = current
        self.camera_controls_cache = {}
        self.camera_controls_cached_at = 0.0
        self.camera_resolutions_cache = {}
        self.camera_resolutions_cached_at = 0.0
        self.camera_request_cache_key = None
        self.camera_request_cache = None
        self.save_settings()
        self.apply_camera_controls()
        if self.inference_active():
            camera_debug("AppState.set_camera_settings restarting camera because inference is active")
            camera_index, camera_resolution = self.camera_request_settings()
            self.camera.start(
                camera_index,
                camera_resolution,
            )
            self.inference_last_frame_id = 0
        camera_debug(f"AppState.set_camera_settings saved={current}")
        return dict(current)

    def camera_control_state(self) -> dict:
        now = time.time()
        if self.camera_controls_cache and now - self.camera_controls_cached_at < 2.0:
            return dict(self.camera_controls_cache)
        camera_index, _ = self.camera_request_settings()
        controls = camera_exposure_controls(camera_index)
        self.camera_controls_cache = dict(controls)
        self.camera_controls_cached_at = now
        return controls

    def camera_resolution_state(self) -> dict:
        now = time.time()
        if self.camera_resolutions_cache and now - self.camera_resolutions_cached_at < 10.0:
            return dict(self.camera_resolutions_cache)
        camera_index, _ = self.camera_request_settings()
        resolutions = list_camera_resolutions(camera_index)
        self.camera_resolutions_cache = dict(resolutions)
        self.camera_resolutions_cached_at = now
        return resolutions

    def apply_camera_controls(self) -> dict:
        controls = dict(self.settings.get("camera_controls") or {})
        if not controls:
            return self.camera_control_state()
        camera_index, _ = self.camera_request_settings()
        camera_debug(f"AppState.apply_camera_controls index={camera_index} controls={controls}")
        return set_exposure_controls(
            camera_index,
            auto_exposure=controls.get("auto_exposure"),
            exposure_time=controls.get("exposure_time"),
            dynamic_framerate=controls.get("dynamic_framerate"),
        )

    def set_camera_controls(self, controls: dict) -> dict:
        current = dict(self.settings.get("camera_controls") or {})
        if "auto_exposure" in controls:
            current["auto_exposure"] = bool(controls.get("auto_exposure"))
        if "exposure_time" in controls:
            current["exposure_time"] = int(controls.get("exposure_time"))
        if "dynamic_framerate" in controls:
            current["dynamic_framerate"] = bool(controls.get("dynamic_framerate"))
        self.settings["camera_controls"] = current
        result = self.apply_camera_controls()
        self.camera_controls_cache = dict(result)
        self.camera_controls_cached_at = time.time()
        self.save_settings()
        return result

    def handle_firmware_command(self, command: dict) -> None:
        drive = self.drive.apply_pwm(
            float(command.get("left", 0.0)),
            float(command.get("right", 0.0)),
            "firmware",
            float(command.get("mower", 0.0)),
        )
        self.add_log(
            "drive",
            f"firmware pwm: {command.get('state', '-')}",
            command_left=float(command.get("left", 0.0)),
            command_right=float(command.get("right", 0.0)),
            command_mower=float(command.get("mower", 0.0)),
            applied_left=float(drive.get("left", 0.0)),
            applied_right=float(drive.get("right", 0.0)),
            applied_mower=float(drive.get("mower", 0.0)),
            drive_enabled=bool(drive.get("enabled")),
            can_connected=bool(drive.get("can_connected")),
        )

    def add_firmware_log(self, kind: str, message: str, fields: dict) -> None:
        self.add_log(kind, message, **fields)
        if kind == "robot_event":
            threading.Thread(
                target=play_robot_event_sound,
                args=(message, self.add_log),
                name=f"RobotEventSound-{message}",
                daemon=True,
            ).start()

    def save_classification_state(self, running: bool, profile: str = "") -> None:
        self.settings["classification"] = {
            "running": bool(running),
            "profile": profile if running else "",
        }
        self.save_settings()

    def restore_classification_if_enabled(self) -> None:
        classification = self.settings.get("classification") or {}
        if not classification.get("running"):
            return
        profile = slugify(str(classification.get("profile") or self.selected_profile))
        try:
            profile_dir = self.profile_dir(profile)
        except FileNotFoundError:
            self.save_classification_state(False)
            self.add_log("test", f"classification restore skipped: profile not found: {profile}")
            return
        with self.lock:
            self.testing = {"running": True, "profile": profile_dir.name, "last": None, "error": ""}
            self.inference_last_result = None
        self.start_inference()
        self.add_log("test", f"live test restored: profile={profile_dir.name}", profile=profile_dir.name)

    def ensure_profile(self, name: str) -> Path:
        pid = slugify(name)
        profile = PROFILE_ROOT / pid
        for split in ALLOWED_SPLITS:
            for label in DEFAULT_LABELS:
                (profile / "images" / split / label).mkdir(parents=True, exist_ok=True)
        meta = profile / "meta.json"
        if not meta.exists():
            meta.write_text(json.dumps({
                "id": pid,
                "name": name,
                "created": time.time(),
                "camera_crop": DEFAULT_CAMERA_CROP,
            }, indent=2), encoding="utf-8")
        else:
            current = self.read_meta(profile)
            if "camera_crop" not in current or current.get("camera_crop") == OLD_FULL_FRAME_CROP:
                current["camera_crop"] = DEFAULT_CAMERA_CROP
                self.write_meta(profile, current)
        return profile

    def read_meta(self, profile: Path) -> dict:
        try:
            meta = json.loads((profile / "meta.json").read_text(encoding="utf-8"))
        except Exception:
            meta = {"id": profile.name, "name": profile.name}
        meta["camera_crop"] = normalize_crop(meta.get("camera_crop"))
        return meta

    def write_meta(self, profile: Path, meta: dict) -> None:
        meta["camera_crop"] = normalize_crop(meta.get("camera_crop"))
        (profile / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def migrate_default_crops(self) -> None:
        for profile in PROFILE_ROOT.iterdir():
            if not profile.is_dir():
                continue
            meta = self.read_meta(profile)
            if meta.get("camera_crop") == OLD_FULL_FRAME_CROP:
                meta["camera_crop"] = DEFAULT_CAMERA_CROP
                self.write_meta(profile, meta)

    def profile_dir(self, pid: str | None = None) -> Path:
        pid = slugify(pid or self.selected_profile)
        path = PROFILE_ROOT / pid
        if not path.exists():
            raise FileNotFoundError(pid)
        return path

    def list_profiles(self) -> list[dict]:
        profiles = []
        for path in sorted(PROFILE_ROOT.iterdir()):
            if not path.is_dir():
                continue
            meta = self.read_meta(path)
            meta["counts"] = self.count_images(path)
            meta["has_model"] = (path / "models" / "latest" / "model.tflite").exists()
            profiles.append(meta)
        return profiles

    def count_images(self, profile: Path) -> dict:
        counts = {}
        for split in sorted(ALLOWED_SPLITS):
            counts[split] = {}
            for label in DEFAULT_LABELS:
                folder = profile / "images" / split / label
                counts[split][label] = len([p for p in folder.glob("*") if p.is_file()])
        return counts

    def list_images(self, pid: str) -> list[dict]:
        profile = self.profile_dir(pid)
        images = []
        for split in sorted(ALLOWED_SPLITS):
            for label in DEFAULT_LABELS:
                folder = profile / "images" / split / label
                for p in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                    if p.is_file():
                        rel = p.relative_to(profile).as_posix()
                        images.append({
                            "path": rel,
                            "split": split,
                            "label": label,
                            "name": p.name,
                            "mtime": p.stat().st_mtime,
                            "url": f"/api/image?profile={profile.name}&path={rel}",
                        })
        return images

    def state(self) -> dict:
        with self.lock:
            self.ensure_selected_profile_exists()
            images = []
            if self.selected_profile:
                try:
                    images = self.list_images(self.selected_profile)
                except Exception:
                    images = []
            firmware = self.firmware.snapshot()
            return {
                "profiles": self.list_profiles(),
                "selected_profile": self.selected_profile,
                "images": images,
                "camera_crop": self.get_camera_crop(self.selected_profile) if self.selected_profile else DEFAULT_CAMERA_CROP,
                "training": self.training,
                "testing": self.testing,
                "firmware": firmware,
                "robot_state": firmware.get("robot_state", "IDLE"),
                "robot_auto_enabled": self.robot_is_auto(),
                "joystick": dict(self.joystick),
                "drive": self.drive.snapshot(),
                "classification_ms": self.inference_ms,
                "camera_stats": self.camera.snapshot(),
                "camera_controls": self.camera_control_state(),
                "camera_resolutions": self.camera_resolution_state(),
                "system": self.system_state(),
                "logs": list(self.logs),
                "labels": DEFAULT_LABELS,
                "camera_error": self.camera.last_error,
                "camera_resolution": self.camera.resolution,
                "settings": dict(self.settings),
                "time": time.time(),
            }

    def robot_plot_state(self) -> dict:
        with self.lock:
            testing_last = dict(self.testing.get("last") or {})
            firmware = self.firmware.snapshot()
            firmware_last = dict(firmware.get("last") or {})
            return {
                "testing_last": testing_last,
                "firmware_last": firmware_last,
                "classification_ms": self.inference_ms,
                "camera_stats": self.camera.snapshot(),
                "time": time.time(),
            }

    def add_log(self, kind: str, message: str, **fields) -> None:
        entry = {
            "time": time.time(),
            "kind": kind,
            "message": message,
        }
        entry.update(fields)
        self.append_session_log_file(entry)
        with self.lock:
            self.logs.append(entry)
            self.logs = self.logs[-500:]

    def clear_logs(self) -> None:
        with self.lock:
            self.logs = []

    def shutdown(self) -> None:
        self.firmware.set_robot_state("IDLE", self.selected_profile)
        self.inference_stop.set()
        thread = self.inference_thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self.firmware.stop()
        self.camera.stop()
        self.drive.stop()

    def request_system_power_action(self, action: str, *, play_sound: bool = False) -> dict:
        action = str(action or "").lower()
        commands = {
            "shutdown": [["systemctl", "poweroff"], ["shutdown", "-h", "now"]],
            "reboot": [["systemctl", "reboot"], ["shutdown", "-r", "now"]],
        }
        if action not in commands:
            raise ValueError(f"invalid system action: {action}")
        self.add_log("system", f"system {action} requested")
        self.stop_robot()

        def run_action() -> None:
            if play_sound:
                play_shutdown_sound(self.add_log)
            time.sleep(1.0)
            last_error = ""
            try:
                for command in commands[action]:
                    result = subprocess.run(command, check=False, capture_output=True, text=True)
                    if result.returncode == 0:
                        return
                    last_error = (result.stderr or result.stdout or f"return code {result.returncode}").strip()
            except Exception as exc:
                last_error = str(exc)
            self.add_log("error", f"system {action} failed: {last_error}")

        threading.Thread(target=run_action, name=f"System{action.title()}", daemon=True).start()
        return {"action": action, "scheduled": True}

    def get_camera_crop(self, pid: str) -> dict:
        profile = self.profile_dir(pid)
        return normalize_crop(self.read_meta(profile).get("camera_crop"))

    def set_camera_crop(self, pid: str, crop: dict) -> dict:
        profile = self.profile_dir(pid)
        meta = self.read_meta(profile)
        meta["camera_crop"] = normalize_crop(crop)
        self.write_meta(profile, meta)
        return meta["camera_crop"]

    def save_image_bytes(self, pid: str, split: str, label: str, data: bytes, suffix: str = ".jpg") -> dict:
        if split not in ALLOWED_SPLITS:
            raise ValueError("invalid split")
        if label not in ALLOWED_LABELS:
            raise ValueError("invalid label")
        profile = self.profile_dir(pid)
        folder = profile / "images" / split / label
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{now_ms()}_{hashlib.sha1(data).hexdigest()[:8]}{suffix.lower()}"
        path = folder / name
        path.write_bytes(data)
        rel = path.relative_to(profile).as_posix()
        result = {"path": rel, "url": f"/api/image?profile={profile.name}&path={rel}"}
        self.add_log("data", f"image saved: {profile.name}/{rel}", profile=profile.name, split=split, label=label)
        return result

    def move_image(self, pid: str, rel_path: str, split: str, label: str) -> dict:
        if split not in ALLOWED_SPLITS or label not in ALLOWED_LABELS:
            raise ValueError("invalid target")
        profile = self.profile_dir(pid)
        src = (profile / rel_path).resolve()
        if profile.resolve() not in src.parents or not src.exists():
            raise FileNotFoundError(rel_path)
        dst_dir = profile / "images" / split / label
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        if dst.exists():
            dst = dst_dir / f"{now_ms()}_{src.name}"
        shutil.move(str(src), str(dst))
        rel = dst.relative_to(profile).as_posix()
        self.add_log("data", f"image moved: {rel}", profile=profile.name, split=split, label=label)
        return {"path": rel, "url": f"/api/image?profile={profile.name}&path={rel}"}

    def delete_image(self, pid: str, rel_path: str) -> None:
        profile = self.profile_dir(pid)
        target = (profile / rel_path).resolve()
        if profile.resolve() not in target.parents or not target.exists():
            raise FileNotFoundError(rel_path)
        target.unlink()
        self.add_log("data", f"image deleted: {rel_path}", profile=profile.name)

    def start_training(self, pid: str, epochs: int, batch_size: int) -> None:
        profile = self.profile_dir(pid)
        with self.lock:
            if self.training["running"]:
                raise RuntimeError("training already running")
            was_testing = bool(self.testing.get("running"))
            self.testing["running"] = False
            self.testing["error"] = ""
            self.inference_last_result = None
            self.training = {"running": True, "profile": profile.name, "metrics": [], "error": ""}
        if was_testing:
            self.save_classification_state(False)
        self.stop_inference_if_idle()
        if was_testing:
            self.add_log("test", "classification stopped before training", profile=profile.name)
        self.add_log("train", f"training started: profile={profile.name} epochs={epochs} batch={batch_size}")

        def metric(payload):
            with self.lock:
                if payload.get("type") == "metric":
                    self.training["metrics"].append(payload)
                self.training["last"] = payload
            if payload.get("type") == "metric":
                self.add_log(
                    "metric",
                    "epoch {epoch}/{epochs} loss={loss:.4f} acc={accuracy:.4f} val_loss={val_loss:.4f} val_acc={val_accuracy:.4f}".format(**payload),
                    profile=profile.name,
                    epoch=payload.get("epoch"),
                    loss=payload.get("loss"),
                    accuracy=payload.get("accuracy"),
                    val_loss=payload.get("val_loss"),
                    val_accuracy=payload.get("val_accuracy"),
                )
            elif payload.get("type") == "started":
                architecture = payload.get("architecture", "custom")
                self.add_log(
                    "train",
                    f"trainer initialized: architecture={architecture} labels={','.join(payload.get('labels', []))}",
                    profile=profile.name,
                )
            elif payload.get("type") == "finished":
                self.add_log("train", f"training finished: model={payload.get('model_dir', '')}", profile=profile.name)

        def run():
            try:
                train_profile(profile, epochs=epochs, batch_size=batch_size, on_metric=metric)
                with self.lock:
                    self.training["running"] = False
                    self.training["finished"] = time.time()
                    if self.selected_profile == profile.name:
                        self.classifier = None
                        self.classifier_profile = ""
            except Exception as exc:
                with self.lock:
                    self.training["running"] = False
                    self.training["error"] = str(exc)
                self.add_log("error", f"training failed: {exc}", profile=profile.name)

        threading.Thread(target=run, daemon=True).start()

    def start_test(self, pid: str) -> None:
        profile = self.profile_dir(pid)
        with self.lock:
            self.testing = {"running": True, "profile": profile.name, "last": None, "error": ""}
            self.inference_last_result = None
        self.save_classification_state(True, profile.name)
        self.start_inference()
        self.add_log("test", f"live test started: profile={profile.name}")

    def stop_test(self) -> None:
        with self.lock:
            profile = self.testing.get("profile", "")
            self.testing["running"] = False
        self.save_classification_state(False)
        self.stop_inference_if_idle()
        self.add_log("test", f"live test stopped: profile={profile}")

    def inference_profile(self) -> str:
        with self.lock:
            if self.robot_is_auto():
                return self.selected_profile
            if self.testing.get("running"):
                return str(self.testing.get("profile") or self.selected_profile)
            classification = self.settings.get("classification") or {}
            if classification.get("running"):
                return slugify(str(classification.get("profile") or self.selected_profile))
            return ""

    def inference_active(self) -> bool:
        with self.lock:
            classification = self.settings.get("classification") or {}
            return bool(self.robot_is_auto() or self.testing.get("running") or classification.get("running"))

    def robot_is_auto(self) -> bool:
        return self.firmware.robot_is_auto()

    def start_inference(self) -> None:
        camera_index, resolution = self.camera_request_settings()
        self.camera.start(camera_index, resolution)
        with self.lock:
            if self.inference_thread and self.inference_thread.is_alive():
                return
            self.inference_stop.clear()
            self.inference_last_frame_id = 0
            self.motion_estimator.reset()
            self.inference_thread = threading.Thread(target=self.inference_loop, name="AIMowerInference", daemon=True)
            self.inference_thread.start()

    def stop_inference_if_idle(self) -> None:
        if self.inference_active():
            return
        self.inference_stop.set()
        thread = self.inference_thread
        if thread and thread.is_alive():
            thread.join(timeout=1.0)
        self.inference_ms = 0.0
        self.inference_last_at = 0.0
        self.inference_last_frame_id = 0
        self.inference_debug_last_logged = 0.0

    def hardware_stop_monitor_loop(self) -> None:
        release_eval_delay_seconds = 1.0
        final_action_window_seconds = 5.0
        stop_button_actions = (
            (1, 1.0, "start", "START"),
            (2, 3.0, "shutdown", "shutdown"),
            (3, 5.0, "reboot", "reboot"),
            (4, 7.0, "mowing_off", "mowing off"),
            (5, 10.0, "mowing_on", "mowing on"),
        )
        while True:
            try:
                drive_state = self.drive.snapshot()
                pressed = bool(drive_state.get("stop_button_pressed"))
                if pressed and not self.hardware_stop_pressed_last:
                    updated = float(drive_state.get("stop_button_updated") or 0.0)
                    self.hardware_stop_pressed_since = updated or time.time()
                    self.hardware_stop_announced_seconds = 0
                    self.hardware_stop_announced_at = 0.0
                    self.hardware_stop_action_valid_until = 0.0
                    self.add_log("robot", "hardware STOP pressed")
                    self.hardware_stop_action_last_at = time.time()
                    self.stop_robot()
                elif not pressed and self.hardware_stop_pressed_last:
                    pressed_since = self.hardware_stop_pressed_since
                    updated = float(drive_state.get("stop_button_updated") or 0.0)
                    released_at = updated if updated > pressed_since else time.time()
                    if (
                        self.hardware_stop_announced_seconds > 0
                        and released_at >= self.hardware_stop_announced_at + release_eval_delay_seconds
                        and released_at <= self.hardware_stop_action_valid_until
                    ):
                        action_seconds = self.hardware_stop_announced_seconds
                    else:
                        action_seconds = 0
                    self.hardware_stop_pressed_since = 0.0
                    self.hardware_stop_announced_seconds = 0
                    self.hardware_stop_announced_at = 0.0
                    self.hardware_stop_action_valid_until = 0.0
                    self.add_log("robot", "hardware STOP released")
                    if action_seconds >= 1:
                        self.hardware_stop_action_last_at = time.time()
                        self.handle_hardware_stop_release_action(action_seconds)
                self.hardware_stop_pressed_last = pressed

                if pressed and self.hardware_stop_pressed_since > 0:
                    now = time.time()
                    held_for = now - self.hardware_stop_pressed_since
                    due_actions = [
                        (action_seconds, prompt, next_prompt_at)
                        for index, (action_seconds, prompt_at, prompt, _label) in enumerate(stop_button_actions)
                        for next_prompt_at in [
                            stop_button_actions[index + 1][1]
                            if index + 1 < len(stop_button_actions)
                            else prompt_at + final_action_window_seconds
                        ]
                        if self.hardware_stop_announced_seconds < action_seconds and prompt_at <= held_for
                    ]
                    if due_actions:
                        seconds, prompt, next_prompt_at = due_actions[-1]
                        self.hardware_stop_announced_seconds = seconds
                        self.hardware_stop_announced_at = now
                        prompt_at = next(
                            scheduled_at for action_seconds, scheduled_at, _prompt, _label in stop_button_actions if action_seconds == seconds
                        )
                        self.hardware_stop_action_valid_until = now + (next_prompt_at - prompt_at)
                        play_stop_button_prompt(prompt, self.add_log)
            except Exception as exc:
                self.add_log("error", f"hardware STOP monitor failed: {exc}")
                time.sleep(1.0)
            time.sleep(0.2)

    def handle_hardware_stop_release_action(self, action_seconds: int) -> None:
        if action_seconds == 1:
            self.add_log("robot", "hardware STOP held 1s: START")
            self.start_robot(allow_hardware_stop=True, play_sound=False)
            play_stop_button_prompt("start", self.add_log, blocking=True)
            play_robot_start_sound(self.add_log)
        elif action_seconds == 2:
            self.add_log("system", "hardware STOP held 2s: shutdown")
            self.stop_robot()
            play_stop_button_prompt("shutdown", self.add_log, blocking=True)
            self.request_system_power_action("shutdown", play_sound=True)
        elif action_seconds == 3:
            self.add_log("system", "hardware STOP held 3s: reboot")
            self.stop_robot()
            play_stop_button_prompt("reboot", self.add_log, blocking=True)
            self.request_system_power_action("reboot", play_sound=False)
        elif action_seconds == 4:
            self.add_log("robot", "hardware STOP held 4s: mowing off")
            self.set_drive_options({"mower_enabled": False})
            play_stop_button_prompt("mowing_off", self.add_log)
        elif action_seconds >= 5:
            self.add_log("robot", "hardware STOP held 5s: mowing on")
            self.set_drive_options({"mower_enabled": True})
            play_stop_button_prompt("mowing_on", self.add_log)

    def load_classifier_for_profile(self, profile: str) -> TextureClassifier:
        if self.classifier is not None and self.classifier_profile == profile:
            return self.classifier
        model_dir = self.profile_dir(profile) / "models" / "latest"
        self.classifier = TextureClassifier(model_dir)
        self.classifier_profile = profile
        self.add_log("test", f"model loaded: profile={profile}", profile=profile)
        return self.classifier

    def camera_request_settings(self) -> tuple[int, tuple[int, int]]:
        camera = self.settings.get("camera") or {}
        key = (str(camera.get("index", "auto")), str(camera.get("resolution", "1280x720")))
        if self.camera_request_cache_key == key and self.camera_request_cache is not None:
            return self.camera_request_cache
        parsed = (
            parse_camera_index(camera.get("index", "auto")),
            parse_camera_resolution(camera.get("resolution", "1280x720")),
        )
        self.camera_request_cache_key = key
        self.camera_request_cache = parsed
        camera_debug(f"AppState.camera_request_settings raw={camera} parsed=({parsed[0]}, {parsed[1][0]}x{parsed[1][1]})")
        return parsed

    def inference_loop(self) -> None:
        self.add_log("test", "inference loop started")
        while not self.inference_stop.is_set():
            profile = self.inference_profile()
            if not profile:
                time.sleep(0.2)
                continue
            try:
                classifier = self.load_classifier_for_profile(profile)
                camera_index, resolution = self.camera_request_settings()
                latest = self.camera.latest_frame(
                    camera_index,
                    resolution,
                    after_frame_id=self.inference_last_frame_id,
                    timeout=1.0,
                )
                if latest is None:
                    raise RuntimeError(self.camera.last_error or "Camera frame read timed out")
                frame = latest["frame"]
                crop = bottom_aligned_crop(self.get_camera_crop(profile))
                lookahead = lookahead_crop(crop)
                started = time.time()
                cropped_frame = crop_frame(frame, crop)
                result = classifier.classify(cropped_frame)
                lookahead_result = classifier.classify(crop_frame(frame, lookahead)) if lookahead.get("enabled") else None
                overlay_result = dict(result)
                overlay_result["crop"] = crop
                overlay_result["lookahead_crop"] = lookahead
                overlay_result["lookahead_result"] = lookahead_result
                now = time.time()
                motion = self.motion_estimator.update(cropped_frame, now)
                elapsed_ms = (now - started) * 1000.0
                self.inference_ms = elapsed_ms if self.inference_ms <= 0 else (0.8 * self.inference_ms) + (0.2 * elapsed_ms)
                self.inference_last_at = now
                payload = {
                    "label": DISPLAY_LABELS.get(result["label"], result["label"]),
                    "score": round(result["score"], 3),
                    "lawn_score": round(result["grass_score"], 3),
                    "grass_score": result["grass_score"],
                    "lookahead_label": DISPLAY_LABELS.get(lookahead_result["label"], lookahead_result["label"]) if lookahead_result else "",
                    "lookahead_score": round(lookahead_result["score"], 3) if lookahead_result else 0.0,
                    "lookahead_lawn_score": round(lookahead_result["grass_score"], 3) if lookahead_result else 0.0,
                    "lookahead_grass_score": lookahead_result["grass_score"] if lookahead_result else 0.0,
                    "motion": motion,
                    "updated": now,
                }
                with self.lock:
                    self.inference_last_frame_id = int(latest["id"])
                    self.inference_last_result = overlay_result
                    self.testing["last"] = payload
                    if self.testing.get("running"):
                        self.testing["error"] = ""
                self.firmware.set_external_detection(profile, payload, camera_index)
                if now - self.inference_debug_last_logged >= 2.0:
                    camera_stats = self.camera.snapshot()
                    self.add_log(
                        "debug",
                        "classification",
                        profile=profile,
                        label=payload["label"],
                        grass_score=float(payload["grass_score"]),
                        lookahead_label=payload["lookahead_label"],
                        lookahead_grass_score=float(payload["lookahead_grass_score"]),
                        score=float(payload["score"]),
                        motion_score=float(motion.get("turn_score") or 0.0),
                        motion_dx=float(motion.get("dx") or 0.0),
                        motion_net_dx=float(motion.get("net_dx") or 0.0),
                        motion_position_dx=float(motion.get("position_dx") or 0.0),
                        motion_vertical_velocity_px_s=float(motion.get("vertical_velocity_px_s") or 0.0),
                        motion_consistency=float(motion.get("consistency") or 0.0),
                        motion_points=int(motion.get("point_count") or 0),
                        classification_ms=float(self.inference_ms),
                        camera_fps=float(camera_stats.get("fps") or 0.0),
                        camera_frame_id=int(camera_stats.get("frame_id") or 0),
                        classified_frame_id=int(latest["id"]),
                    )
                    self.inference_debug_last_logged = now
                time.sleep(self.inference_interval)
            except Exception as exc:
                message = str(exc)
                with self.lock:
                    if self.testing.get("running"):
                        self.testing["error"] = message
                self.firmware.set_external_status("error", profile, message)
                camera_stats = self.camera.snapshot()
                self.add_log(
                    "error",
                    f"inference failed: {message}",
                    profile=profile,
                    camera_fps=float(camera_stats.get("fps") or 0.0),
                    camera_frame_id=int(camera_stats.get("frame_id") or 0),
                    camera_error=camera_stats.get("error", ""),
                )
                time.sleep(1.0)
        self.add_log("test", "inference loop stopped")

    def render_detection(self, frame):
        with self.lock:
            result = self.inference_last_result
        return draw_detection_overlay(frame, result) if result else frame

    def start_robot(self, *, allow_hardware_stop: bool = False, play_sound: bool = True) -> None:
        if self.drive.snapshot().get("stop_button_pressed") and not allow_hardware_stop:
            self.stop_robot()
            self.add_log("robot", "robot start blocked: hardware STOP pressed", profile=self.selected_profile)
            return
        self.drive.start()
        self.firmware.start(self.selected_profile)
        self.firmware.set_robot_state("AUTO", self.selected_profile)
        self.save_classification_state(True, self.selected_profile)
        self.start_inference()
        self.add_log("robot", f"robot control started: profile={self.selected_profile}", profile=self.selected_profile)
        if play_sound:
            play_robot_start_sound(self.add_log)

    def stop_robot(self) -> None:
        was_active = self.robot_is_auto() or bool(self.drive.snapshot().get("enabled"))
        self.firmware.set_joystick_active(False)
        with self.lock:
            self.joystick["active"] = False
            self.joystick["left"] = 0.0
            self.joystick["right"] = 0.0
            self.joystick["x"] = 0.0
            self.joystick["y"] = 0.0
        self.firmware.set_robot_state("IDLE", self.selected_profile)
        self.drive.stop()
        self.add_log("robot", "robot state changed to IDLE", profile=self.selected_profile)
        if was_active:
            play_robot_stop_sound(self.add_log)

    def play_sheep_sound(self) -> None:
        play_robot_sheep_sound(self.add_log)

    def set_drive_options(self, options: dict) -> dict:
        state = self.drive.set_options(
            swap_sides=options.get("swap_sides"),
            invert_left=options.get("invert_left"),
            invert_right=options.get("invert_right"),
            pwm_scale=options.get("pwm_scale"),
            pwm_ramp_rate=options.get("pwm_ramp_rate"),
            mower_pwm_ramp_rate=options.get("mower_pwm_ramp_rate"),
            mower_enabled=options.get("mower_enabled"),
            mower_pwm=options.get("mower_pwm"),
        )
        drive_options = state.get("options", {})
        self.settings["drive_options"] = dict(drive_options)
        self.save_settings()
        self.add_log(
            "robot",
            "drive options saved: swap_sides={swap_sides} invert_left={invert_left} invert_right={invert_right} pwm_scale={pwm_scale:.2f} pwm_ramp_rate={pwm_ramp_rate:.2f} mower_pwm_ramp_rate={mower_pwm_ramp_rate:.2f} mower_enabled={mower_enabled} mower_pwm={mower_pwm:.2f}".format(**drive_options),
        )
        return state

    def read_cpu_sample(self) -> tuple[int, int] | None:
        try:
            line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
            parts = [int(value) for value in line.split()[1:]]
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
            return sum(parts), idle
        except Exception:
            return None

    def read_cpu_temperature_c(self) -> float | None:
        thermal_zones = sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
        preferred_names = ("cpu", "soc", "package", "x86_pkg_temp")
        fallback = None
        for zone in thermal_zones:
            try:
                temp_path = zone / "temp"
                raw_temp = float(temp_path.read_text(encoding="utf-8").strip())
                temp_c = raw_temp / 1000.0 if raw_temp > 200.0 else raw_temp
                if not -40.0 <= temp_c <= 150.0:
                    continue
                type_path = zone / "type"
                zone_type = type_path.read_text(encoding="utf-8").strip().lower() if type_path.exists() else ""
                if fallback is None:
                    fallback = temp_c
                if any(name in zone_type for name in preferred_names):
                    return temp_c
            except Exception:
                continue
        return fallback

    def system_state(self) -> dict:
        cpu_percent = None
        sample = self.read_cpu_sample()
        if sample and self.system_cpu_sample:
            total_delta = sample[0] - self.system_cpu_sample[0]
            idle_delta = sample[1] - self.system_cpu_sample[1]
            if total_delta > 0:
                cpu_percent = max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))
        if sample:
            self.system_cpu_sample = sample

        mem_total = 0
        mem_available = 0
        try:
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                key, value = line.split(":", 1)
                if key == "MemTotal":
                    mem_total = int(value.strip().split()[0])
                elif key == "MemAvailable":
                    mem_available = int(value.strip().split()[0])
            ram_percent = 100.0 * (1.0 - mem_available / mem_total) if mem_total > 0 else None
        except Exception:
            ram_percent = None

        try:
            usage = shutil.disk_usage(ROOT)
            disk_percent = 100.0 * usage.used / usage.total if usage.total > 0 else None
        except Exception:
            disk_percent = None

        return {
            "cpu_percent": cpu_percent,
            "cpu_temperature_c": self.read_cpu_temperature_c(),
            "ram_percent": ram_percent,
            "disk_percent": disk_percent,
        }

    def set_auto_options(self, options: dict) -> dict:
        auto_options = self.firmware.set_auto_options(
            forward_speed=options.get("forward_speed"),
            turn_speed=options.get("turn_speed"),
            mower_auto_pwm=options.get("mower_auto_pwm"),
            turn_reverse_seconds=options.get("turn_reverse_seconds"),
            turn_stall_reverse_seconds=options.get("turn_stall_reverse_seconds"),
            turn_stall_min_seconds=options.get("turn_stall_min_seconds"),
            turn_stall_min_position_delta=options.get("turn_stall_min_position_delta"),
            turn_pause_seconds=options.get("turn_pause_seconds"),
            turn_stall_recovery_enabled=options.get("turn_stall_recovery_enabled"),
            drive_stall_recovery_enabled=options.get("drive_stall_recovery_enabled"),
            drive_stall_min_seconds=options.get("drive_stall_min_seconds"),
            drive_stall_min_velocity=options.get("drive_stall_min_velocity"),
            drive_stall_min_points=options.get("drive_stall_min_points"),
        )
        self.settings["auto_options"] = dict(auto_options)
        self.save_settings()
        self.add_log(
            "robot",
            "auto options saved: forward_speed={forward_speed:.2f} turn_speed={turn_speed:.2f} mower_auto_pwm={mower_auto_pwm:.2f} turn_reverse_seconds={turn_reverse_seconds:.2f} turn_stall_reverse_seconds={turn_stall_reverse_seconds:.2f} turn_stall_min_seconds={turn_stall_min_seconds:.2f} turn_stall_min_position_delta={turn_stall_min_position_delta:.1f} turn_pause_seconds={turn_pause_seconds:.2f} turn_stall_recovery_enabled={turn_stall_recovery_enabled} drive_stall_recovery_enabled={drive_stall_recovery_enabled} drive_stall_min_seconds={drive_stall_min_seconds:.2f} drive_stall_min_velocity={drive_stall_min_velocity:.1f} drive_stall_min_points={drive_stall_min_points}".format(**auto_options),
        )
        return auto_options

    def set_joystick(self, x: float, y: float, active: bool, log: bool = False, seq=None, client_time_ms=None) -> dict:
        now = time.time()
        if active and self.drive.snapshot().get("stop_button_pressed"):
            self.stop_robot()
            with self.lock:
                state = dict(self.joystick)
                state["hardware_stop"] = True
            return state
        try:
            seq = int(seq)
        except (TypeError, ValueError):
            seq = None
        try:
            client_time_ms = float(client_time_ms)
        except (TypeError, ValueError):
            client_time_ms = None

        x = max(-1.0, min(1.0, float(x)))
        y = max(-1.0, min(1.0, float(y)))
        forward = -y
        turn = x
        left = max(-1.0, min(1.0, forward + turn))
        right = max(-1.0, min(1.0, forward - turn))
        with self.lock:
            previous_seq = int(self.joystick.get("seq") or 0)
            previous_updated = float(self.joystick.get("updated") or 0.0)
            if seq is not None and seq <= previous_seq and now - previous_updated < 2.0:
                state = dict(self.joystick)
                state["stale"] = True
                state["ignored_seq"] = seq
                return state
            age_ms = None
            if client_time_ms is not None:
                server_now_ms = now * 1000.0
                if abs(server_now_ms - client_time_ms) < 600000.0:
                    age_ms = max(0.0, server_now_ms - client_time_ms)
            if active and age_ms is not None and age_ms > 30000.0:
                state = dict(self.joystick)
                state["stale"] = True
                state["ignored_seq"] = seq
                state["age_ms"] = age_ms
                return state
            self.joystick = {
                "x": x,
                "y": y,
                "left": left,
                "right": right,
                "active": bool(active),
                "updated": now,
                "seq": seq if seq is not None else previous_seq,
                "client_time_ms": client_time_ms,
                "age_ms": age_ms,
                "stale": False,
            }
            state = dict(self.joystick)
        self.firmware.set_joystick_active(active)
        if active:
            self.drive.start()
            self.firmware.start(self.selected_profile)
            self.start_inference()
            self.drive.apply_pwm(left, right, "joystick", 1.0)
        else:
            self.drive.apply_pwm(0.0, 0.0, "joystick", 0.0)
        if log:
            self.add_log("robot", f"joystick x={x:.2f} y={y:.2f} left={left:.2f} right={right:.2f}")
        return state
