from __future__ import annotations

from collections import deque

import cv2
import numpy as np


class VisualTurnMotionEstimator:
    def __init__(
        self,
        *,
        max_width: int = 320,
        window_seconds: float = 1.0,
        noise_px: float = 0.15,
        turn_px_threshold: float = 8.0,
        min_points: int = 12,
        max_points: int = 160,
    ):
        self.max_width = max_width
        self.window_seconds = window_seconds
        self.noise_px = noise_px
        self.turn_px_threshold = turn_px_threshold
        self.min_points = min_points
        self.max_points = max_points
        self.prev = None
        self.prev_at = 0.0
        self.position_dx = 0.0
        self.window = deque()

    def reset(self) -> None:
        self.prev = None
        self.prev_at = 0.0
        self.position_dx = 0.0
        self.window.clear()

    def update(self, frame, now: float) -> dict:
        current = self._prepare(frame)
        if current is None:
            self.reset()
            return self._empty(now, "invalid_frame")

        if self.prev is None or self.prev.shape != current.shape:
            self.prev = current
            self.prev_at = now
            return self._empty(now, "priming")

        dt = max(0.001, now - self.prev_at)
        points = cv2.goodFeaturesToTrack(
            self.prev,
            maxCorners=self.max_points,
            qualityLevel=0.01,
            minDistance=8,
            blockSize=7,
        )
        if points is None or len(points) < self.min_points:
            self.prev = current
            self.prev_at = now
            return self._empty(now, "not_enough_features")

        next_points, status, _ = cv2.calcOpticalFlowPyrLK(
            self.prev,
            current,
            points,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
        )
        self.prev = current
        self.prev_at = now

        if next_points is None or status is None:
            return self._empty(now, "invalid_motion")

        valid = status.reshape(-1) == 1
        if int(valid.sum()) < self.min_points:
            return self._empty(now, "not_enough_tracked_features")

        flow = (next_points.reshape(-1, 2) - points.reshape(-1, 2))[valid]
        finite = np.isfinite(flow).all(axis=1)
        flow = flow[finite]
        if len(flow) < self.min_points:
            return self._empty(now, "invalid_motion")

        dx_values = flow[:, 0]
        dy_values = flow[:, 1]
        dx = float(np.median(dx_values))
        dy = float(np.median(dy_values))
        if abs(dx) >= self.noise_px:
            self.position_dx += dx
        point_count = int(len(flow))
        response = point_count / max(1, self.max_points)

        self.window.append((now, dx, dy, response, dt, point_count))
        while self.window and self.window[0][0] < now - self.window_seconds:
            self.window.popleft()

        useful = [item for item in self.window if abs(item[1]) >= self.noise_px]
        positive = sum(1 for _, x, *_ in useful if x > 0)
        negative = sum(1 for _, x, *_ in useful if x < 0)
        consistency = max(positive, negative) / max(1, len(useful))
        net_dx = sum(item[1] for item in self.window)
        net_dy = sum(item[2] for item in self.window)
        total_dt = sum(item[4] for item in self.window)
        avg_response = sum(item[3] for item in self.window) / max(1, len(self.window))
        avg_point_count = sum(item[5] for item in self.window) / max(1, len(self.window))
        horizontal_ratio = abs(net_dx) / max(abs(net_dx) + abs(net_dy), 1e-6)
        vertical_velocity_px_s = net_dy / max(total_dt, 1e-6)
        response_factor = max(0.0, min(1.0, avg_point_count / max(1, self.min_points * 2)))
        score = min(1.0, abs(net_dx) / self.turn_px_threshold) * consistency * horizontal_ratio * response_factor

        return {
            "updated": now,
            "dx": float(dx),
            "dy": float(dy),
            "dt": float(dt),
            "response": float(response),
            "net_dx": float(net_dx),
            "net_dy": float(net_dy),
            "position_dx": float(self.position_dx),
            "vertical_velocity_px_s": float(vertical_velocity_px_s),
            "horizontal_ratio": float(horizontal_ratio),
            "consistency": float(consistency),
            "turn_score": float(max(0.0, min(1.0, score))),
            "turn_direction": "right" if net_dx > 0 else ("left" if net_dx < 0 else "none"),
            "point_count": point_count,
            "status": "tracking",
        }

    def _prepare(self, frame):
        if frame is None or getattr(frame, "size", 0) == 0:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        height, width = gray.shape[:2]
        if width <= 4 or height <= 4:
            return None
        if width > self.max_width:
            scale = self.max_width / width
            gray = cv2.resize(gray, (self.max_width, max(4, int(height * scale))), interpolation=cv2.INTER_AREA)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        gray = cv2.equalizeHist(gray)
        if float(gray.std()) <= 1e-6:
            return None
        return gray

    def _empty(self, now: float, status: str) -> dict:
        return {
            "updated": now,
            "dx": 0.0,
            "dy": 0.0,
            "dt": 0.0,
            "response": 0.0,
            "net_dx": 0.0,
            "net_dy": 0.0,
            "position_dx": float(self.position_dx),
            "vertical_velocity_px_s": 0.0,
            "horizontal_ratio": 0.0,
            "consistency": 0.0,
            "turn_score": 0.0,
            "turn_direction": "none",
            "point_count": 0,
            "status": status,
        }
