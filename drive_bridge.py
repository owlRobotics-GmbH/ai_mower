from __future__ import annotations

import os
import threading
import time

from diffdrive import DifferentialDriveRobot


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return parse_bool(value, default)


def parse_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def clamp_pwm(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def clamp_ramp_rate(value: float) -> float:
    return max(0.0, min(10.0, float(value)))


class DiffDrivePwmBridge:
    def __init__(self):
        self.lock = threading.Lock()
        self.enabled = False
        self.output_enabled = env_bool("AI_MOWER_MOTOR_OUTPUT", True)
        self.pwm_scale = max(0.0, min(1.0, env_float("AI_MOWER_PWM_SCALE", 1.0)))
        self.pwm_ramp_rate = clamp_ramp_rate(env_float("AI_MOWER_PWM_RAMP_RATE", 1.0))
        self.mower_pwm_ramp_rate = clamp_ramp_rate(env_float("AI_MOWER_MOWER_PWM_RAMP_RATE", 0.25))
        self.mower_enabled = env_bool("AI_MOWER_MOWER_ENABLED", True)
        self.mower_pwm = max(0.0, min(1.0, env_float("AI_MOWER_MOWER_PWM", 1.0)))
        self.ramp_interval_seconds = max(0.02, min(0.20, env_float("AI_MOWER_PWM_RAMP_INTERVAL", 0.05)))
        self.battery_request_interval_seconds = max(1.0, min(60.0, env_float("AI_MOWER_BATTERY_INTERVAL", 5.0)))
        self.last_battery_request_at = 0.0
        self.stop_button_request_interval_seconds = max(0.2, min(10.0, env_float("AI_MOWER_STOP_BUTTON_INTERVAL", 0.5)))
        self.last_stop_button_request_at = 0.0
        self.motor_current_request_interval_seconds = max(0.2, min(10.0, env_float("AI_MOWER_MOTOR_CURRENT_INTERVAL", 1.0)))
        self.last_motor_current_request_at = 0.0
        self.joystick_timeout_seconds = max(0.2, min(5.0, env_float("AI_MOWER_JOYSTICK_TIMEOUT", 1.5)))
        self.swap_sides = env_bool("AI_MOWER_SWAP_SIDES", False)
        self.invert_left = env_bool("AI_MOWER_SWAP_LEFT", False)
        self.invert_right = env_bool("AI_MOWER_SWAP_RIGHT", False)
        self.current_left = 0.0
        self.current_right = 0.0
        self.current_mower = 0.0
        self.target_left = 0.0
        self.target_right = 0.0
        self.target_mower = 0.0
        self.target_source = "init"
        self.target_updated_at = time.time()
        self.last_ramp_at = time.time()
        self.stop_event = threading.Event()
        self.ramp_thread = threading.Thread(target=self._ramp_loop, name="DiffDrivePwmRamp", daemon=True)
        self.robot = DifferentialDriveRobot(
            os.environ.get("AI_MOWER_ROBOT_NAME", "ai_mower"),
            env_float("AI_MOWER_WHEEL_CENTER_Y", 0.20),
            env_float("AI_MOWER_WHEEL_DIA", 0.20),
            env_float("AI_MOWER_GEAR_RATIO", 1.0),
            False,
            False,
            False,
        )
        self.last = {
            "enabled": False,
            "output_enabled": self.output_enabled,
            "can_connected": self.robot.bus is not None,
            "left": 0.0,
            "right": 0.0,
            "mower": 0.0,
            "battery_voltage": 0.0,
            "stop_button_pressed": False,
            "stop_button_updated": 0.0,
            "stop_button_age_ms": None,
            "left_current": 0.0,
            "right_current": 0.0,
            "mower_current": 0.0,
            "drive_current": 0.0,
            "target_left": 0.0,
            "target_right": 0.0,
            "target_mower": 0.0,
            "source": "init",
            "target_updated": self.target_updated_at,
            "joystick_timeout_seconds": self.joystick_timeout_seconds,
            "options": self.options(),
            "updated": 0.0,
        }
        self.ramp_thread.start()

    def options(self) -> dict:
        return {
            "swap_sides": self.swap_sides,
            "invert_left": self.invert_left,
            "invert_right": self.invert_right,
            "pwm_scale": self.pwm_scale,
            "pwm_ramp_rate": self.pwm_ramp_rate,
            "mower_pwm_ramp_rate": self.mower_pwm_ramp_rate,
            "mower_enabled": self.mower_enabled,
            "mower_pwm": self.mower_pwm,
        }

    def set_options(self, *, swap_sides=None, invert_left=None, invert_right=None, pwm_scale=None, pwm_ramp_rate=None, mower_pwm_ramp_rate=None, mower_enabled=None, mower_pwm=None) -> dict:
        with self.lock:
            if swap_sides is not None:
                self.swap_sides = parse_bool(swap_sides, self.swap_sides)
            if invert_left is not None:
                self.invert_left = parse_bool(invert_left, self.invert_left)
            if invert_right is not None:
                self.invert_right = parse_bool(invert_right, self.invert_right)
            if pwm_scale is not None:
                self.pwm_scale = max(0.0, min(1.0, float(pwm_scale)))
            if pwm_ramp_rate is not None:
                self.pwm_ramp_rate = clamp_ramp_rate(pwm_ramp_rate)
            if mower_pwm_ramp_rate is not None:
                self.mower_pwm_ramp_rate = clamp_ramp_rate(mower_pwm_ramp_rate)
            if mower_enabled is not None:
                self.mower_enabled = parse_bool(mower_enabled, self.mower_enabled)
            if mower_pwm is not None:
                self.mower_pwm = max(0.0, min(1.0, float(mower_pwm)))
            if not self.mower_enabled:
                self.target_mower = 0.0
            self.last["options"] = self.options()
            self.last["updated"] = time.time()
            return dict(self.last)

    def start(self) -> dict:
        with self.lock:
            was_enabled = self.enabled
            self.enabled = True
            if self.output_enabled and not was_enabled:
                self.robot.enableMotors(True)
            self.last_ramp_at = time.time()
            self.last.update({"enabled": True, "source": "start", "updated": time.time()})
            self.last["can_connected"] = self.robot.bus is not None
            self.last["options"] = self.options()
            self._request_battery_voltage_locked(time.time(), force=True)
            self._request_stop_button_state_locked(time.time(), force=True)
            self._request_motor_currents_locked(time.time(), force=True)
            return dict(self.last)

    def stop(self) -> dict:
        with self.lock:
            self.target_left = 0.0
            self.target_right = 0.0
            self.target_mower = 0.0
            self.current_left = 0.0
            self.current_right = 0.0
            self.current_mower = 0.0
            self._send_pwm_locked(0.0, 0.0, 0.0, "stop")
            if self.output_enabled:
                self.robot.enableMotors(False)
            self.enabled = False
            self.last.update({"enabled": False, "source": "stop", "updated": time.time()})
            self.last["can_connected"] = self.robot.bus is not None
            self.last["options"] = self.options()
            self._update_battery_voltage_locked()
            self._update_stop_button_state_locked()
            self._update_motor_currents_locked()
            return dict(self.last)

    def apply_pwm(self, left: float, right: float, source: str, mower: float = 0.0) -> dict:
        with self.lock:
            if not self.enabled:
                self.target_left = 0.0
                self.target_right = 0.0
                self.target_mower = 0.0
                self.current_left = 0.0
                self.current_right = 0.0
                self.current_mower = 0.0
                self.last.update({
                    "enabled": False,
                    "can_connected": self.robot.bus is not None,
                    "left": 0.0,
                    "right": 0.0,
                    "mower": 0.0,
                    "battery_voltage": self.robot.batteryVoltage,
                    **self._stop_button_state_locked(),
                    **self._motor_current_state_locked(),
                    "target_left": 0.0,
                    "target_right": 0.0,
                    "target_mower": 0.0,
                    "source": "disabled",
                    "options": self.options(),
                    "updated": time.time(),
                })
                return dict(self.last)
            self.target_left, self.target_right = self._transform_pwm_locked(left, right)
            self.target_mower = self._transform_mower_pwm_locked(mower)
            self.target_source = source
            self.target_updated_at = time.time()
            self._ramp_step_locked(time.time(), source)
            return dict(self.last)

    def _transform_pwm_locked(self, left: float, right: float) -> tuple[float, float]:
        left = clamp_pwm(left) * self.pwm_scale
        right = clamp_pwm(right) * self.pwm_scale
        if self.swap_sides:
            left, right = right, left
        if self.invert_left:
            left *= -1.0
        if self.invert_right:
            right *= -1.0
        return left, right

    def _transform_mower_pwm_locked(self, mower: float) -> float:
        if not self.mower_enabled:
            return 0.0
        return max(0.0, clamp_pwm(mower)) * self.mower_pwm

    def _move_toward(self, current: float, target: float, max_delta: float) -> float:
        delta = target - current
        if abs(delta) <= max_delta:
            return target
        return current + max_delta * (1.0 if delta > 0 else -1.0)

    def _ramp_step_locked(self, now: float, source: str | None = None) -> None:
        elapsed = max(0.0, now - self.last_ramp_at)
        self.last_ramp_at = now
        if self.pwm_ramp_rate <= 0:
            self.current_left = self.target_left
            self.current_right = self.target_right
        else:
            max_delta = self.pwm_ramp_rate * elapsed
            self.current_left = self._move_toward(self.current_left, self.target_left, max_delta)
            self.current_right = self._move_toward(self.current_right, self.target_right, max_delta)
        mower_ramp_rate = self.mower_pwm_ramp_rate
        if abs(self.target_mower) < abs(self.current_mower):
            mower_ramp_rate = max(mower_ramp_rate, 2.0)
        if mower_ramp_rate <= 0:
            self.current_mower = self.target_mower
        else:
            mower_max_delta = mower_ramp_rate * elapsed
            self.current_mower = self._move_toward(self.current_mower, self.target_mower, mower_max_delta)
        self._send_pwm_locked(self.current_left, self.current_right, self.current_mower, source or self.target_source)

    def _send_pwm_locked(self, left: float, right: float, mower: float, source: str) -> None:
        if self.output_enabled:
            self.robot.setMotorPwmSpeed(left, right, mower)
        self.last.update({
            "enabled": self.enabled,
            "output_enabled": self.output_enabled,
            "can_connected": self.robot.bus is not None,
            "left": left,
            "right": right,
            "mower": mower,
            "battery_voltage": self.robot.batteryVoltage,
            **self._stop_button_state_locked(),
            **self._motor_current_state_locked(),
            "target_left": self.target_left,
            "target_right": self.target_right,
            "target_mower": self.target_mower,
            "source": source,
            "target_updated": self.target_updated_at,
            "joystick_timeout_seconds": self.joystick_timeout_seconds,
            "options": self.options(),
            "updated": time.time(),
        })

    def _ramp_loop(self) -> None:
        while not self.stop_event.is_set():
            time.sleep(self.ramp_interval_seconds)
            with self.lock:
                now = time.time()
                self._request_battery_voltage_locked(now)
                self._request_stop_button_state_locked(now)
                self._request_motor_currents_locked(now)
                self._update_battery_voltage_locked()
                self._update_stop_button_state_locked()
                self._update_motor_currents_locked()
                if not self.enabled:
                    continue
                if self.target_source == "joystick" and now - self.target_updated_at > self.joystick_timeout_seconds:
                    self.target_left = 0.0
                    self.target_right = 0.0
                    self.target_mower = 0.0
                    self.target_source = "joystick_timeout"
                    self.target_updated_at = now
                if self.current_left == self.target_left and self.current_right == self.target_right and self.current_mower == self.target_mower:
                    self.last_ramp_at = now
                    continue
                self._ramp_step_locked(now)

    def snapshot(self) -> dict:
        with self.lock:
            self._update_battery_voltage_locked()
            self._update_stop_button_state_locked()
            self._update_motor_currents_locked()
            return dict(self.last)

    def _request_battery_voltage_locked(self, now: float, *, force: bool = False) -> None:
        if self.robot.bus is None:
            return
        if not force and now - self.last_battery_request_at < self.battery_request_interval_seconds:
            return
        self.last_battery_request_at = now
        self.robot.requestBatteryVoltage()

    def _update_battery_voltage_locked(self) -> None:
        self.last["battery_voltage"] = float(self.robot.batteryVoltage or 0.0)

    def _request_stop_button_state_locked(self, now: float, *, force: bool = False) -> None:
        if self.robot.bus is None:
            return
        if not force and now - self.last_stop_button_request_at < self.stop_button_request_interval_seconds:
            return
        self.last_stop_button_request_at = now
        self.robot.requestStopButtonState()

    def _stop_button_state_locked(self) -> dict:
        updated = float(getattr(self.robot, "stopButtonUpdated", 0.0) or 0.0)
        return {
            "stop_button_pressed": bool(getattr(self.robot, "stopButtonPressed", False)),
            "stop_button_updated": updated,
            "stop_button_age_ms": max(0.0, (time.time() - updated) * 1000.0) if updated else None,
        }

    def _update_stop_button_state_locked(self) -> None:
        self.last.update(self._stop_button_state_locked())

    def _request_motor_currents_locked(self, now: float, *, force: bool = False) -> None:
        if self.robot.bus is None:
            return
        if not force and now - self.last_motor_current_request_at < self.motor_current_request_interval_seconds:
            return
        self.last_motor_current_request_at = now
        self.robot.requestMotorCurrents()

    def _motor_current_state_locked(self) -> dict:
        currents = getattr(self.robot, "motorCurrents", {}) or {}
        left = float(currents.get(1, 0.0) or 0.0)
        right = float(currents.get(2, 0.0) or 0.0)
        mower = float(currents.get(3, 0.0) or 0.0)
        return {
            "left_current": left,
            "right_current": right,
            "mower_current": mower,
            "drive_current": left + right,
        }

    def _update_motor_currents_locked(self) -> None:
        self.last.update(self._motor_current_state_locked())
