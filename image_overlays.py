from __future__ import annotations

import cv2

from model_runtime import normalize_crop


def draw_crop_box(frame, crop: dict | None):
    crop = normalize_crop(crop)
    if not crop["enabled"]:
        return frame
    out = frame.copy()
    fh, fw = out.shape[:2]
    x1 = int(round(crop["x"] * fw))
    y1 = int(round(crop["y"] * fh))
    x2 = int(round((crop["x"] + crop["w"]) * fw))
    y2 = int(round((crop["y"] + crop["h"]) * fh))
    cv2.rectangle(out, (x1, y1), (x2, y2), (255, 185, 45), 3)
    cv2.putText(out, "ROI", (x1 + 10, max(28, y1 + 28)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 185, 45), 2)
    return out
