from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import select
import struct
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2

from app_state import AppState, DEFAULT_LABELS, ROOT
from audio import play_startup_sound
from camera_manager import (
    DEFAULT_CAMERA_INDEX,
    DEFAULT_CAMERA_RESOLUTION,
    camera_debug,
    parse_camera_index,
    parse_camera_resolution,
)
from fast_depth_runtime import FastDepthRuntime
from image_overlays import draw_crop_box
from segmentation_runtime import SegmentationRuntime


WEB_ROOT = ROOT / "web"
APP: AppState | None = None
FAST_DEPTH: FastDepthRuntime | None = None
SEGMENTATION: SegmentationRuntime | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "AIMower/0.1"

    def log_message(self, fmt, *args):
        if getattr(self.server, "access_log", False):
            super().log_message(fmt, *args)

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        return json.loads(body.decode("utf-8") or "{}")

    def do_GET(self):
        assert APP is not None
        assert FAST_DEPTH is not None
        assert SEGMENTATION is not None
        parsed = urlparse(self.path)
        if parsed.path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            self.handle_ws()
            return
        if parsed.path == "/api/state":
            state = APP.state()
            state["fast_depth"] = FAST_DEPTH.snapshot()
            state["segmentation"] = SEGMENTATION.snapshot()
            self.send_json(state)
            return
        if parsed.path == "/api/robot/plot_state":
            self.send_json(APP.robot_plot_state())
            return
        if parsed.path == "/api/image":
            self.serve_profile_image(parsed)
            return
        if parsed.path == "/api/camera.mjpg":
            camera, resolution, view = self.camera_request(parsed)
            self.serve_mjpeg(test=False, camera=camera, resolution=resolution, view=view)
            return
        if parsed.path == "/api/test.mjpg":
            camera, resolution, view = self.camera_request(parsed)
            self.serve_mjpeg(test=True, camera=camera, resolution=resolution, view=view)
            return
        self.serve_static(parsed.path)

    def do_POST(self):
        assert APP is not None
        try:
            parsed = urlparse(self.path)
            data = self.read_json()
            if parsed.path == "/api/profiles":
                profile = APP.ensure_profile(str(data.get("name", "profile")))
                APP.select_profile(profile.name)
                APP.add_log("profile", f"profile selected/created: {profile.name}", profile=profile.name)
                self.send_json({"ok": True, "profile": profile.name})
            elif parsed.path == "/api/select_profile":
                profile = APP.select_profile(str(data.get("profile", "")))
                APP.add_log("profile", f"profile selected: {profile}", profile=profile)
                self.send_json({"ok": True, "profile": profile})
            elif parsed.path == "/api/upload_image":
                pid = str(data.get("profile") or APP.selected_profile)
                split = str(data.get("split", "train"))
                label = str(data.get("label", DEFAULT_LABELS[0]))
                raw = str(data.get("data", ""))
                suffix = ".jpg"
                if "," in raw:
                    header, raw = raw.split(",", 1)
                    if "png" in header:
                        suffix = ".png"
                img = base64.b64decode(raw)
                self.send_json({"ok": True, "image": APP.save_image_bytes(pid, split, label, img, suffix)})
            elif parsed.path == "/api/capture_image":
                pid = str(data.get("profile") or APP.selected_profile)
                split = str(data.get("split", "train"))
                label = str(data.get("label", DEFAULT_LABELS[0]))
                camera = parse_camera_index(data.get("camera", DEFAULT_CAMERA_INDEX))
                resolution = parse_camera_resolution(data.get("resolution", DEFAULT_CAMERA_RESOLUTION))
                img = APP.camera.snapshot_jpeg(camera, APP.get_camera_crop(pid), resolution)
                self.send_json({"ok": True, "image": APP.save_image_bytes(pid, split, label, img, ".jpg")})
            elif parsed.path == "/api/camera_crop":
                pid = str(data.get("profile") or APP.selected_profile)
                crop = APP.set_camera_crop(pid, data.get("crop") or {})
                APP.add_log(
                    "camera",
                    "camera ROI saved: enabled={enabled} x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f}".format(**crop),
                    profile=pid,
                )
                self.send_json({"ok": True, "camera_crop": crop})
            elif parsed.path == "/api/camera_settings":
                camera_debug(f"HTTP POST /api/camera_settings body={data}")
                camera = APP.set_camera_settings(data.get("camera"), data.get("resolution"))
                APP.add_log("camera", f"camera settings saved: index={camera['index']} resolution={camera['resolution']}")
                self.send_json({"ok": True, "camera": camera})
            elif parsed.path == "/api/camera_controls":
                controls = APP.set_camera_controls(data)
                APP.add_log("camera", "camera controls saved")
                self.send_json({"ok": True, "camera_controls": controls})
            elif parsed.path == "/api/move_image":
                self.send_json({"ok": True, "image": APP.move_image(
                    str(data.get("profile") or APP.selected_profile),
                    str(data.get("path", "")),
                    str(data.get("split", "train")),
                    str(data.get("label", DEFAULT_LABELS[0])),
                )})
            elif parsed.path == "/api/delete_image":
                APP.delete_image(str(data.get("profile") or APP.selected_profile), str(data.get("path", "")))
                self.send_json({"ok": True})
            elif parsed.path == "/api/train":
                APP.start_training(
                    str(data.get("profile") or APP.selected_profile),
                    int(data.get("epochs", 16)),
                    int(data.get("batch_size", 16)),
                )
                self.send_json({"ok": True})
            elif parsed.path == "/api/test/start":
                APP.start_test(str(data.get("profile") or APP.selected_profile))
                self.send_json({"ok": True})
            elif parsed.path == "/api/test/stop":
                APP.stop_test()
                self.send_json({"ok": True})
            elif parsed.path == "/api/robot/start":
                APP.start_robot()
                self.send_json({"ok": True})
            elif parsed.path == "/api/robot/stop":
                APP.stop_robot()
                self.send_json({"ok": True})
            elif parsed.path == "/api/robot/say_maeh":
                APP.play_sheep_sound()
                self.send_json({"ok": True})
            elif parsed.path == "/api/robot/joystick":
                joystick = APP.set_joystick(
                    float(data.get("x", 0.0)),
                    float(data.get("y", 0.0)),
                    bool(data.get("active", False)),
                    seq=data.get("seq"),
                    client_time_ms=data.get("client_time_ms"),
                )
                self.send_json({"ok": True, "joystick": joystick})
            elif parsed.path == "/api/robot/drive_options":
                drive = APP.set_drive_options(data)
                self.send_json({"ok": True, "drive": drive})
            elif parsed.path == "/api/robot/auto_options":
                auto_options = APP.set_auto_options(data)
                self.send_json({"ok": True, "auto_options": auto_options})
            elif parsed.path == "/api/system/power":
                result = APP.request_system_power_action(
                    str(data.get("action", "")),
                    play_sound=bool(data.get("play_sound", False)),
                )
                self.send_json({"ok": True, **result})
            elif parsed.path == "/api/logs/clear":
                APP.clear_logs()
                APP.add_log("system", "log cleared")
                self.send_json({"ok": True})
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")
        except Exception as exc:
            APP.add_log("error", f"request failed: {parsed.path}: {exc}")
            self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def camera_request(self, parsed) -> tuple[int, tuple[int, int], str]:
        qs = parse_qs(parsed.query)
        camera = parse_camera_index(qs.get("camera", [DEFAULT_CAMERA_INDEX])[0])
        resolution = parse_camera_resolution(qs.get("resolution", [DEFAULT_CAMERA_RESOLUTION])[0])
        view = str(qs.get("view", ["rgb"])[0]).lower()
        if view not in {"rgb", "depth", "seg"}:
            view = "rgb"
        camera_debug(f"HTTP camera_request path={parsed.path} query={parsed.query!r} parsed=({camera}, {resolution[0]}x{resolution[1]}, view={view})")
        return camera, resolution, view

    def serve_profile_image(self, parsed):
        qs = parse_qs(parsed.query)
        profile = APP.profile_dir(qs.get("profile", [APP.selected_profile])[0])
        rel = qs.get("path", [""])[0]
        target = (profile / rel).resolve()
        if profile.resolve() not in target.parents or not target.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        self.send_file(target, cache="no-cache")

    def serve_static(self, path: str):
        if path == "/":
            path = "/index.html"
        target = (WEB_ROOT / path.lstrip("/")).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        self.send_file(target, cache="no-cache, must-revalidate")

    def send_file(self, target: Path, cache: str):
        body = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix == ".js":
            ctype = "application/javascript"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_mjpeg(
        self,
        test: bool,
        camera: int | str = DEFAULT_CAMERA_INDEX,
        resolution: tuple[int, int] | None = None,
        view: str = "rgb",
    ):
        camera = parse_camera_index(camera)
        resolution = resolution or parse_camera_resolution()
        camera_debug(f"HTTP serve_mjpeg start test={test} camera={camera} resolution={resolution[0]}x{resolution[1]} view={view}")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        while True:
            try:
                frame = APP.camera.read(camera, resolution, timeout=3.0)
                crop = APP.get_camera_crop(APP.testing.get("profile") or APP.selected_profile)
                if view == "depth":
                    frame = FAST_DEPTH.render(frame)
                elif view == "seg":
                    frame = SEGMENTATION.render(frame)
                elif test:
                    frame = APP.render_detection(frame)
                elif not test:
                    frame = draw_crop_box(frame, crop)
                ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                if not ok:
                    continue
                jpg = bytes(buf)
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n")
                self.wfile.write(jpg + b"\r\n")
                time.sleep(0.08)
            except Exception as exc:
                camera_debug(f"HTTP serve_mjpeg error test={test} camera={camera}: {exc}")
                with APP.lock:
                    if test:
                        APP.testing["error"] = str(exc)
                    APP.camera.last_error = str(exc)
                break
        camera_debug(f"HTTP serve_mjpeg end test={test} camera={camera} view={view}")

    def handle_ws(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing Sec-WebSocket-Key")
            return
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.request.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: " + accept.encode() + b"\r\n\r\n"
        )
        self.request.settimeout(0.0)
        while True:
            try:
                self.ws_send(json.dumps(APP.state()))
                self.ws_read_discard()
                time.sleep(0.5)
            except Exception:
                break

    def ws_send(self, data: str):
        payload = data.encode("utf-8")
        hdr = bytearray([0x81])
        n = len(payload)
        if n <= 125:
            hdr.append(n)
        elif n < (1 << 16):
            hdr.append(126)
            hdr.extend(struct.pack("!H", n))
        else:
            hdr.append(127)
            hdr.extend(struct.pack("!Q", n))
        self.request.sendall(hdr + payload)

    def ws_read_discard(self):
        ready, _, _ = select.select([self.request], [], [], 0.0)
        if not ready:
            return
        head = self.request.recv(2)
        if not head:
            raise ConnectionError
        ln = head[1] & 0x7F
        if ln == 126:
            ln = struct.unpack("!H", self.request.recv(2))[0]
        elif ln == 127:
            ln = struct.unpack("!Q", self.request.recv(8))[0]
        if head[1] & 0x80:
            self.request.recv(4)
        if ln:
            self.request.recv(ln)


def main():
    global APP, FAST_DEPTH, SEGMENTATION
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--access-log", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    APP = AppState()
    FAST_DEPTH = FastDepthRuntime()
    SEGMENTATION = SegmentationRuntime()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.access_log = args.access_log
    print(f"AI mower web UI on http://{args.host}:{args.port}")
    play_startup_sound(APP.add_log)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        APP.shutdown()


if __name__ == "__main__":
    main()
