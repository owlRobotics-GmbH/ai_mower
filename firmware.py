from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable


def clamp_speed(value, default: float = 0.30) -> float:
    try:
        speed = float(value)
    except (TypeError, ValueError):
        speed = default
    if speed > 1.0:
        speed /= 100.0
    return max(0.30, min(1.0, speed))


def clamp_seconds(value, default: float, *, minimum: float = 0.2, maximum: float = 5.0) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = default
    return max(minimum, min(maximum, seconds))


def clamp_float(value, default: float, *, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def clamp_int(value, default: int, *, minimum: int, maximum: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


class FirmwareController:
    def __init__(
        self,
        *,
        camera: str = "auto",
        on_threshold: float = 0.70,
        off_threshold: float = 0.55,
        command_callback: Callable[[dict], None] | None = None,
        log_callback: Callable[[str, str, dict], None] | None = None,
    ):
        if off_threshold > on_threshold:
            raise ValueError("off_threshold must be <= on_threshold")
        self.camera = camera
        self.on_threshold = on_threshold
        self.off_threshold = off_threshold
        self.command_callback = command_callback
        self.log_callback = log_callback
        self.forward_speed = 0.50
        self.lookahead_slow_factor = 0.45
        self.lookahead_slow_min_speed = 0.18
        self.turn_speed = 0.50
        self.turn_burst_seconds = 0.80
        self.escape_turn_min_seconds = 1.20
        self.escape_turn_max_seconds = 3.50
        self.escape_turn_max_extra_seconds = 2.00
        self.escape_turn_bursts_remaining = 0
        self.escape_turn_level = 0
        self.current_turn_burst_seconds = self.turn_burst_seconds
        self.turn_reverse_seconds = 0.80
        self.turn_pause_seconds = 2.00
        self.command_repeat_seconds = 0.50
        self.mower_auto_pwm = 1.0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = None
        self.profile = ""
        self.is_lawn = False
        self.robot_state = "IDLE"
        self.joystick_active = False
        self.last_detection_updated = 0.0
        self.last_command_sent_at = 0.0
        self.turn_phase = "turn"
        self.turn_phase_until = 0.0
        self.turn_direction = 1
        self.must_turn_before_forward = False
        self.turn_stall_recovery_enabled = True
        self.drive_stall_recovery_enabled = True
        self.turn_motion_start_position = None
        self.turn_motion_start_at = 0.0
        self.turn_motion_active_seconds = 0.0
        self.turn_motion_last_active_at = 0.0
        self.turn_stall_min_seconds = 2.50
        self.turn_stall_min_position_delta = 15.0
        self.turn_stall_reverse_seconds = 2.0
        self.turn_stall_recovery_count = 0
        self.turn_stall_last_triggered_at = 0.0
        self.turn_stall_last_delta = 0.0
        self.turn_stall_last_elapsed = 0.0
        self.drive_stall_min_seconds = 2.50
        self.drive_stall_min_velocity = 12.0
        self.drive_stall_min_points = 40
        self.drive_stall_started_at = 0.0
        self.drive_stall_last_velocity = 0.0
        self.drive_stall_last_points = 0
        self.drive_stall_recovery_count = 0
        self.drive_stall_last_triggered_at = 0.0
        self.state = {
            "running": False,
            "profile": "",
            "camera": camera,
            "camera_index": None,
            "robot_state": "IDLE",
            "status": "stopped",
            "last": None,
            "command": None,
            "auto_options": self.auto_options(),
            "error": "",
            "updated": 0.0,
        }

    def start(self, profile: str) -> None:
        with self.lock:
            self.profile = profile
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            self.state.update({"running": True, "profile": profile, "status": "starting", "error": "", "robot_state": self.robot_state})
            self.thread = threading.Thread(target=self._loop, name="FirmwareController", daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        with self.lock:
            self.state.update({"running": False, "status": "stopped", "error": "", "robot_state": self.robot_state})

    def set_profile(self, profile: str) -> None:
        with self.lock:
            if self.profile != profile:
                self.is_lawn = False
            self.profile = profile
            self.state["profile"] = profile

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.state)

    def auto_options(self) -> dict:
        return {
            "forward_speed": self.forward_speed,
            "turn_speed": self.turn_speed,
            "mower_auto_pwm": self.mower_auto_pwm,
            "turn_reverse_seconds": self.turn_reverse_seconds,
            "turn_stall_reverse_seconds": self.turn_stall_reverse_seconds,
            "turn_stall_min_seconds": self.turn_stall_min_seconds,
            "turn_stall_min_position_delta": self.turn_stall_min_position_delta,
            "turn_pause_seconds": self.turn_pause_seconds,
            "turn_stall_recovery_enabled": self.turn_stall_recovery_enabled,
            "drive_stall_recovery_enabled": self.drive_stall_recovery_enabled,
            "drive_stall_min_seconds": self.drive_stall_min_seconds,
            "drive_stall_min_velocity": self.drive_stall_min_velocity,
            "drive_stall_min_points": self.drive_stall_min_points,
        }

    def set_auto_options(self, *, forward_speed=None, turn_speed=None, mower_auto_pwm=None, turn_reverse_seconds=None, turn_stall_reverse_seconds=None, turn_stall_min_seconds=None, turn_stall_min_position_delta=None, turn_pause_seconds=None, turn_stall_recovery_enabled=None, drive_stall_recovery_enabled=None, drive_stall_min_seconds=None, drive_stall_min_velocity=None, drive_stall_min_points=None) -> dict:
        with self.lock:
            if forward_speed is not None:
                self.forward_speed = clamp_speed(forward_speed, self.forward_speed)
            if turn_speed is not None:
                self.turn_speed = clamp_speed(turn_speed, self.turn_speed)
            if mower_auto_pwm is not None:
                self.mower_auto_pwm = max(0.0, min(1.0, float(mower_auto_pwm)))
            if turn_reverse_seconds is not None:
                self.turn_reverse_seconds = clamp_seconds(turn_reverse_seconds, self.turn_reverse_seconds, minimum=0.0)
            if turn_stall_reverse_seconds is not None:
                self.turn_stall_reverse_seconds = clamp_seconds(turn_stall_reverse_seconds, self.turn_stall_reverse_seconds, minimum=0.0)
            if turn_stall_min_seconds is not None:
                self.turn_stall_min_seconds = clamp_seconds(turn_stall_min_seconds, self.turn_stall_min_seconds, minimum=0.2, maximum=10.0)
            if turn_stall_min_position_delta is not None:
                self.turn_stall_min_position_delta = clamp_float(turn_stall_min_position_delta, self.turn_stall_min_position_delta, minimum=1.0, maximum=200.0)
            if turn_pause_seconds is not None:
                self.turn_pause_seconds = clamp_seconds(turn_pause_seconds, self.turn_pause_seconds)
            if turn_stall_recovery_enabled is not None:
                self.turn_stall_recovery_enabled = bool(turn_stall_recovery_enabled)
            if drive_stall_recovery_enabled is not None:
                self.drive_stall_recovery_enabled = bool(drive_stall_recovery_enabled)
            if drive_stall_min_seconds is not None:
                self.drive_stall_min_seconds = clamp_seconds(drive_stall_min_seconds, self.drive_stall_min_seconds, minimum=0.2, maximum=10.0)
            if drive_stall_min_velocity is not None:
                self.drive_stall_min_velocity = clamp_float(drive_stall_min_velocity, self.drive_stall_min_velocity, minimum=0.0, maximum=200.0)
            if drive_stall_min_points is not None:
                self.drive_stall_min_points = clamp_int(drive_stall_min_points, self.drive_stall_min_points, minimum=1, maximum=500)
            options = self.auto_options()
            self.state["auto_options"] = options
            self.state["updated"] = time.time()
            return options

    def set_robot_state(self, state: str, profile: str = "") -> None:
        state = str(state or "IDLE").upper()
        if state not in {"AUTO", "IDLE"}:
            raise ValueError(f"invalid robot state: {state}")
        stop_command = None
        with self.lock:
            previous = self.robot_state
            self.robot_state = state
            if profile:
                self.profile = profile
            if state == "AUTO":
                self.last_detection_updated = 0.0
                self._reset_turn_cycle_locked()
            self.state.update({
                "running": self.thread is not None and self.thread.is_alive(),
                "profile": self.profile,
                "robot_state": self.robot_state,
                "status": "auto" if state == "AUTO" else "idle",
                "error": "",
                "updated": time.time(),
            })
            if previous == "AUTO" and state != "AUTO":
                self.is_lawn = False
                self._reset_turn_cycle_locked()
                stop_command = {"left": 0.0, "right": 0.0, "mower": 0.0, "state": "idle"}
                self.state["command"] = stop_command
                self.last_command_sent_at = time.time()
        if stop_command and self.command_callback:
            self.command_callback(stop_command)

    def robot_is_auto(self) -> bool:
        with self.lock:
            return self.robot_state == "AUTO"

    def set_joystick_active(self, active: bool) -> None:
        with self.lock:
            was_active = self.joystick_active
            self.joystick_active = bool(active)
            if was_active and not self.joystick_active:
                self.last_detection_updated = 0.0
                self._reset_turn_cycle_locked()
            if self.joystick_active and self.robot_state == "AUTO":
                self.state["status"] = "manual_override"
                self.state["updated"] = time.time()

    def set_external_detection(self, profile: str, payload: dict, camera_index: int | None = None) -> None:
        self._set_state(
            running=True,
            profile=profile,
            camera=self.camera,
            camera_index=camera_index,
            status="classified",
            last=payload,
            error="",
        )

    def set_external_status(self, status: str, profile: str = "", error: str = "") -> None:
        self._set_state(running=False, profile=profile, status=status, error=error, robot_state=self.robot_state)

    def command_from_detection(self, grass_score: float, motion: dict | None = None, now: float | None = None, lookahead_grass_score: float | None = None) -> tuple[bool, dict]:
        now = now if now is not None else time.time()
        if self._recover_stalled_turn_locked(motion, now):
            self.is_lawn = False
            return False, self.turn_pause_command(now, motion)
        was_lawn = self.is_lawn
        detected_lawn = grass_score > self.off_threshold if self.is_lawn else grass_score >= self.on_threshold
        if detected_lawn and self.must_turn_before_forward:
            self.is_lawn = False
            return False, self.turn_pause_command(now, motion)
        if detected_lawn and self._recover_stalled_drive_locked(motion, now):
            self.is_lawn = False
            return False, self.turn_pause_command(now, motion)
        self.is_lawn = detected_lawn
        if detected_lawn:
            self._reset_turn_cycle_locked(reset_drive_stall=False)
            forward_speed = self._forward_speed_for_lookahead_locked(lookahead_grass_score)
            state = "slow_forward_edge" if forward_speed < self.forward_speed else "forward"
            return True, self._auto_command(forward_speed, forward_speed, state)
        if was_lawn:
            self._log("robot_event", "no_lawn", grass_score=grass_score)
        self._reset_drive_stall_locked()
        if was_lawn or self.turn_phase_until <= 0:
            self._start_turn_reverse_locked(now)
        return False, self.turn_pause_command(now, motion)

    def _reset_turn_cycle_locked(self, *, reset_drive_stall: bool = True) -> None:
        self.turn_phase = "turn"
        self.turn_phase_until = 0.0
        self.turn_direction = 1
        self.must_turn_before_forward = False
        self.turn_motion_start_position = None
        self.turn_motion_start_at = 0.0
        self.turn_motion_active_seconds = 0.0
        self.turn_motion_last_active_at = 0.0
        self.turn_stall_last_delta = 0.0
        self.turn_stall_last_elapsed = 0.0
        self.current_turn_burst_seconds = self.turn_burst_seconds
        self.escape_turn_bursts_remaining = 0
        self.escape_turn_level = 0
        if reset_drive_stall:
            self._reset_drive_stall_locked()

    def _choose_turn_direction_locked(self) -> None:
        self.turn_direction = random.choice([-1, 1])

    def _reset_drive_stall_locked(self) -> None:
        self.drive_stall_started_at = 0.0

    def _forward_speed_for_lookahead_locked(self, lookahead_grass_score: float | None) -> float:
        if lookahead_grass_score is None:
            return self.forward_speed
        if lookahead_grass_score >= self.off_threshold:
            return self.forward_speed
        return max(self.lookahead_slow_min_speed, self.forward_speed * self.lookahead_slow_factor)

    def _arm_escape_turn_locked(self) -> None:
        self.escape_turn_level = min(3, self.escape_turn_level + 1)
        self.escape_turn_bursts_remaining = max(self.escape_turn_bursts_remaining, 2)

    def _choose_turn_burst_seconds_locked(self) -> float:
        if self.escape_turn_bursts_remaining <= 0:
            self.escape_turn_level = 0
            return self.turn_burst_seconds
        extra = self.escape_turn_max_extra_seconds * max(0, self.escape_turn_level - 1)
        duration = random.uniform(
            self.escape_turn_min_seconds,
            self.escape_turn_max_seconds + extra,
        )
        self.escape_turn_bursts_remaining -= 1
        if self.escape_turn_bursts_remaining <= 0:
            self.escape_turn_level = 0
        return duration

    def _start_turn_reverse_locked(self, now: float, seconds: float | None = None) -> None:
        duration = self.turn_reverse_seconds if seconds is None else max(0.0, float(seconds))
        if duration <= 0:
            self._choose_turn_direction_locked()
            self._reset_turn_motion_reference_locked()
            self._start_turn_pause_locked(now)
            return
        self._choose_turn_direction_locked()
        self.turn_phase = "reverse"
        self.turn_phase_until = now + duration
        self.must_turn_before_forward = True
        self.turn_motion_start_position = None
        self.turn_motion_start_at = 0.0
        self.turn_motion_active_seconds = 0.0
        self.turn_motion_last_active_at = 0.0
        self.turn_stall_last_delta = 0.0
        self.turn_stall_last_elapsed = 0.0
        self._reset_drive_stall_locked()

    def _start_turn_burst_locked(self, now: float) -> None:
        self.current_turn_burst_seconds = self._choose_turn_burst_seconds_locked()
        self.turn_phase = "turn"
        self.turn_phase_until = now + self.current_turn_burst_seconds
        if self.turn_motion_start_position is not None:
            self.turn_motion_last_active_at = now

    def _start_turn_pause_locked(self, now: float) -> None:
        if self.turn_phase == "turn":
            self._update_turn_motion_active_time_locked(now)
            self.must_turn_before_forward = False
        self.turn_phase = "pause"
        self.turn_phase_until = now + self.turn_pause_seconds
        self.turn_motion_last_active_at = 0.0

    def _reset_turn_motion_reference_locked(self, position: float | None = None, now: float = 0.0) -> None:
        self.turn_motion_start_position = position
        self.turn_motion_start_at = now if position is not None else 0.0
        self.turn_motion_active_seconds = 0.0
        self.turn_motion_last_active_at = now if position is not None and self.turn_phase == "turn" else 0.0

    def _update_turn_motion_active_time_locked(self, now: float) -> None:
        if self.turn_phase != "turn" or self.turn_motion_start_position is None:
            self.turn_motion_last_active_at = 0.0
            return
        if self.turn_motion_last_active_at <= 0:
            self.turn_motion_last_active_at = now
            return
        self.turn_motion_active_seconds += max(0.0, now - self.turn_motion_last_active_at)
        self.turn_motion_last_active_at = now

    def _recover_stalled_turn_locked(self, motion: dict | None, now: float) -> bool:
        if not self.turn_stall_recovery_enabled:
            return False
        if self.turn_phase != "turn" or not motion:
            return False
        try:
            position = float(motion.get("position_dx"))
        except (TypeError, ValueError):
            return False
        if self.turn_motion_start_position is None:
            self._reset_turn_motion_reference_locked(position, now)
            return False
        self._update_turn_motion_active_time_locked(now)
        elapsed = self.turn_motion_active_seconds
        delta = abs(position - self.turn_motion_start_position)
        self.turn_stall_last_delta = delta
        self.turn_stall_last_elapsed = elapsed
        if delta >= self.turn_stall_min_position_delta:
            self._reset_turn_motion_reference_locked(position, now)
            return False
        if elapsed < self.turn_stall_min_seconds:
            return False
        self.turn_stall_recovery_count += 1
        self.turn_stall_last_triggered_at = now
        self._arm_escape_turn_locked()
        self._start_turn_reverse_locked(now, self.turn_stall_reverse_seconds)
        self.turn_stall_last_delta = delta
        self.turn_stall_last_elapsed = elapsed
        self._log(
            "robot_event",
            "turn_stuck",
            elapsed=elapsed,
            delta=delta,
            min_seconds=self.turn_stall_min_seconds,
            min_delta=self.turn_stall_min_position_delta,
        )
        return True

    def _turn_burst_ended_stalled_locked(self, motion: dict | None, now: float) -> bool:
        if not self.turn_stall_recovery_enabled:
            return False
        if self.turn_phase != "turn" or not motion:
            return False
        try:
            position = float(motion.get("position_dx"))
        except (TypeError, ValueError):
            return False
        if self.turn_motion_start_position is None:
            self._reset_turn_motion_reference_locked(position, now)
            return False
        self._update_turn_motion_active_time_locked(now)
        elapsed = self.turn_motion_active_seconds
        delta = abs(position - self.turn_motion_start_position)
        self.turn_stall_last_delta = delta
        self.turn_stall_last_elapsed = elapsed
        if delta >= self.turn_stall_min_position_delta:
            self._reset_turn_motion_reference_locked(position, now)
            return False
        if elapsed < self.turn_stall_min_seconds:
            return False
        self.turn_stall_recovery_count += 1
        self.turn_stall_last_triggered_at = now
        self._arm_escape_turn_locked()
        self._start_turn_reverse_locked(now, self.turn_stall_reverse_seconds)
        self.turn_stall_last_delta = delta
        self.turn_stall_last_elapsed = elapsed
        self._log(
            "robot_event",
            "turn_stuck",
            elapsed=elapsed,
            delta=delta,
            min_seconds=self.turn_stall_min_seconds,
            min_delta=self.turn_stall_min_position_delta,
        )
        return True

    def _set_turn_motion_reference_locked(self, motion: dict | None, now: float) -> None:
        if self.turn_phase != "turn" or not motion:
            return
        try:
            position = float(motion.get("position_dx"))
        except (TypeError, ValueError):
            return
        if self.turn_motion_start_position is not None:
            if self.turn_motion_last_active_at <= 0:
                self.turn_motion_last_active_at = now
            return
        self._reset_turn_motion_reference_locked(position, now)

    def _recover_stalled_drive_locked(self, motion: dict | None, now: float) -> bool:
        if not self.drive_stall_recovery_enabled or not motion:
            self.drive_stall_last_velocity = 0.0
            self._reset_drive_stall_locked()
            return False
        try:
            velocity = abs(float(motion.get("vertical_velocity_px_s")))
        except (TypeError, ValueError):
            self.drive_stall_last_velocity = 0.0
            self._reset_drive_stall_locked()
            return False
        points = int(motion.get("point_count") or 0)
        self.drive_stall_last_velocity = velocity
        self.drive_stall_last_points = points
        if points < self.drive_stall_min_points or velocity >= self.drive_stall_min_velocity:
            self._reset_drive_stall_locked()
            return False
        if self.drive_stall_started_at <= 0:
            self.drive_stall_started_at = now
            return False
        if now - self.drive_stall_started_at < self.drive_stall_min_seconds:
            return False
        self.drive_stall_recovery_count += 1
        self.drive_stall_last_triggered_at = now
        self._arm_escape_turn_locked()
        self._start_turn_reverse_locked(now, self.turn_stall_reverse_seconds)
        self._log(
            "robot_event",
            "drive_stuck",
            elapsed=now - self.drive_stall_started_at,
            velocity=velocity,
            points=points,
            min_seconds=self.drive_stall_min_seconds,
            min_velocity=self.drive_stall_min_velocity,
            min_points=self.drive_stall_min_points,
        )
        return True

    def _motion_debug_fields_locked(self, detection: dict, now: float) -> dict:
        motion = detection.get("motion") if isinstance(detection, dict) else {}
        if not isinstance(motion, dict):
            motion = {}
        try:
            position = float(motion.get("position_dx"))
        except (TypeError, ValueError):
            position = 0.0
        start = self.turn_motion_start_position
        self._update_turn_motion_active_time_locked(now)
        elapsed = self.turn_motion_active_seconds
        delta = abs(position - start) if start is not None else 0.0
        return {
            "motion_status": motion.get("status", ""),
            "motion_position_dx": position,
            "motion_dx": float(motion.get("dx") or 0.0),
            "motion_net_dx": float(motion.get("net_dx") or 0.0),
            "motion_v_px_s": float(motion.get("vertical_velocity_px_s") or 0.0),
            "motion_points": int(motion.get("point_count") or 0),
            "turn_motion_start_position": start,
            "turn_motion_delta": delta,
            "turn_motion_elapsed": elapsed,
            "turn_stall_min_seconds": self.turn_stall_min_seconds,
            "turn_stall_min_delta": self.turn_stall_min_position_delta,
            "turn_stall_recovery_count": self.turn_stall_recovery_count,
            "turn_stall_recovery_enabled": self.turn_stall_recovery_enabled,
            "turn_stall_triggered": now == self.turn_stall_last_triggered_at,
            "turn_stall_last_delta": self.turn_stall_last_delta,
            "turn_stall_last_elapsed": self.turn_stall_last_elapsed,
            "turn_burst_seconds": self.current_turn_burst_seconds,
            "escape_turn_level": self.escape_turn_level,
            "escape_turn_bursts_remaining": self.escape_turn_bursts_remaining,
            "drive_stall_recovery_enabled": self.drive_stall_recovery_enabled,
            "drive_stall_velocity": self.drive_stall_last_velocity,
            "drive_stall_min_velocity": self.drive_stall_min_velocity,
            "drive_stall_points": self.drive_stall_last_points,
            "drive_stall_min_points": self.drive_stall_min_points,
            "drive_stall_elapsed": now - self.drive_stall_started_at if self.drive_stall_started_at else 0.0,
            "drive_stall_min_seconds": self.drive_stall_min_seconds,
            "drive_stall_recovery_count": self.drive_stall_recovery_count,
            "drive_stall_triggered": now == self.drive_stall_last_triggered_at,
        }

    def turn_pause_command(self, now: float | None = None, motion: dict | None = None) -> dict:
        now = now if now is not None else time.time()
        if self.turn_phase_until <= 0:
            self._start_turn_burst_locked(now)
            self._set_turn_motion_reference_locked(motion, now)
        elif self.turn_phase == "reverse" and now >= self.turn_phase_until:
            self._start_turn_pause_locked(now)
        elif self.turn_phase == "turn" and now >= self.turn_phase_until:
            if not self._turn_burst_ended_stalled_locked(motion, now):
                self._start_turn_pause_locked(now)
        elif self.turn_phase == "pause" and now >= self.turn_phase_until:
            self._start_turn_burst_locked(now)
            self._set_turn_motion_reference_locked(motion, now)

        if self.turn_phase == "reverse":
            return self._auto_command(-self.forward_speed, -self.forward_speed, "reverse_for_turn")
        if self.turn_phase == "pause":
            return self._auto_command(0.0, 0.0, "pause_for_camera")
        return self._auto_command(
            self.turn_speed * self.turn_direction,
            -self.turn_speed * self.turn_direction,
            "turn_to_lawn",
        )

    def _auto_command(self, left: float, right: float, state: str) -> dict:
        return {"left": left, "right": right, "mower": self.mower_auto_pwm, "state": state}

    def _log(self, kind: str, message: str, **fields) -> None:
        if self.log_callback:
            self.log_callback(kind, message, fields)

    def _set_state(self, **fields) -> None:
        with self.lock:
            self.state.update(fields)
            self.state["robot_state"] = self.robot_state
            self.state["updated"] = time.time()

    def _should_send_command_locked(self, candidate: dict, now: float) -> tuple[bool, bool]:
        is_repeat = candidate == self.state.get("command")
        if not is_repeat:
            return True, False
        return now - self.last_command_sent_at >= self.command_repeat_seconds, True

    def _loop(self) -> None:
        self._log("firmware", "firmware loop started without local inference")
        try:
            while not self.stop_event.is_set():
                command = None
                command_log = None
                with self.lock:
                    profile = self.profile
                    detection = dict(self.state.get("last") or {})
                    detection_updated = float(detection.get("updated") or 0.0)
                    robot_state = self.robot_state
                    joystick_active = self.joystick_active
                    now = time.time()

                    has_new_detection = detection_updated > self.last_detection_updated
                    if robot_state == "AUTO" and detection and not joystick_active and has_new_detection:
                        grass_score = float(detection.get("grass_score", detection.get("lawn_score", 0.0)))
                        raw_lookahead = detection.get("lookahead_grass_score", detection.get("lookahead_lawn_score"))
                        lookahead_grass_score = float(raw_lookahead) if raw_lookahead is not None else None
                        _, candidate = self.command_from_detection(grass_score, detection.get("motion"), now, lookahead_grass_score)
                        should_send, is_repeat = self._should_send_command_locked(candidate, now)
                        if should_send:
                            motion_debug = self._motion_debug_fields_locked(detection, now)
                            command = candidate
                            self.state["command"] = command
                            self.last_command_sent_at = now
                            command_log = {
                                "grass_score": grass_score,
                                "lookahead_grass_score": lookahead_grass_score,
                                "is_lawn": self.is_lawn,
                                "turn_phase": self.turn_phase,
                                "turn_direction": self.turn_direction,
                                "repeat": is_repeat,
                                "detection_age_ms": (now - detection_updated) * 1000.0,
                                **motion_debug,
                                **command,
                            }
                        self.state["status"] = "auto"
                    elif robot_state == "AUTO" and detection and not joystick_active and not self.is_lawn:
                        candidate = self.turn_pause_command(now, detection.get("motion"))
                        should_send, is_repeat = self._should_send_command_locked(candidate, now)
                        if should_send:
                            raw_lookahead = detection.get("lookahead_grass_score", detection.get("lookahead_lawn_score"))
                            lookahead_grass_score = float(raw_lookahead) if raw_lookahead is not None else None
                            motion_debug = self._motion_debug_fields_locked(detection, now)
                            command = candidate
                            self.state["command"] = command
                            self.last_command_sent_at = now
                            command_log = {
                                "grass_score": float(detection.get("grass_score", detection.get("lawn_score", 0.0))),
                                "lookahead_grass_score": lookahead_grass_score,
                                "is_lawn": self.is_lawn,
                                "turn_phase": self.turn_phase,
                                "turn_direction": self.turn_direction,
                                "repeat": is_repeat,
                                "detection_age_ms": (now - detection_updated) * 1000.0 if detection_updated else 0.0,
                                **motion_debug,
                                **command,
                            }
                        self.state["status"] = "auto"
                    elif robot_state == "AUTO" and detection and not joystick_active and self.is_lawn:
                        raw_lookahead = detection.get("lookahead_grass_score", detection.get("lookahead_lawn_score"))
                        lookahead_grass_score = float(raw_lookahead) if raw_lookahead is not None else None
                        forward_speed = self._forward_speed_for_lookahead_locked(lookahead_grass_score)
                        forward_state = "slow_forward_edge" if forward_speed < self.forward_speed else "forward"
                        candidate = self._auto_command(forward_speed, forward_speed, forward_state)
                        should_send, is_repeat = self._should_send_command_locked(candidate, now)
                        if should_send:
                            motion_debug = self._motion_debug_fields_locked(detection, now)
                            command = candidate
                            self.state["command"] = command
                            self.last_command_sent_at = now
                            command_log = {
                                "grass_score": float(detection.get("grass_score", detection.get("lawn_score", 0.0))),
                                "lookahead_grass_score": lookahead_grass_score,
                                "is_lawn": self.is_lawn,
                                "turn_phase": self.turn_phase,
                                "turn_direction": self.turn_direction,
                                "repeat": is_repeat,
                                "detection_age_ms": (now - detection_updated) * 1000.0 if detection_updated else 0.0,
                                **motion_debug,
                                **command,
                            }
                        self.state["status"] = "auto"
                    elif robot_state == "AUTO" and joystick_active:
                        self.state["status"] = "manual_override"
                    elif has_new_detection:
                        self.state["status"] = "classified"
                    elif robot_state == "AUTO":
                        self.state["status"] = "auto"
                    else:
                        self.state["status"] = "idle"

                    self.last_detection_updated = max(self.last_detection_updated, detection_updated)
                    self.state.update({
                        "running": True,
                        "profile": profile,
                        "camera": self.camera,
                        "robot_state": robot_state,
                        "error": "",
                        "updated": now,
                    })

                if command_log:
                    self._log("auto", f"command: {command_log.get('state', '-')}", **command_log)
                if command and self.command_callback:
                    self.command_callback(command)
                time.sleep(0.1)
        except Exception as exc:
            self._set_state(running=False, status="error", error=str(exc))
            self._log("error", f"firmware loop failed: {exc}")
        finally:
            if self.stop_event.is_set():
                self._set_state(running=False, status="stopped", error="")
            else:
                self._set_state(running=self.snapshot().get("running", False))
            self._log("firmware", "firmware loop stopped")
