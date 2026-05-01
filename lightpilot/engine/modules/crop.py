"""Crop and rotation module.

Supports:
- CropTop/CropBottom/CropLeft/CropRight: normalized [0, 1] crop bounds.
- CropAngle: rotation in degrees (small angles for horizon correction).
"""

from __future__ import annotations

import numpy as np
import cv2

from .base import BaseModule
from ..buffer import ImageBuffer


class CropModule(BaseModule):

    @property
    def name(self) -> str:
        return "crop"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        angle = params.get("CropAngle", 0.0)   # degrees
        top = params.get("CropTop", 0.0)        # 0..1
        bottom = params.get("CropBottom", 1.0)   # 0..1
        left = params.get("CropLeft", 0.0)       # 0..1
        right = params.get("CropRight", 1.0)     # 0..1

        img = buf.data
        h, w = img.shape[:2]

        # --- Rotation ---
        if abs(angle) > 0.01:
            center = (w / 2.0, h / 2.0)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(
                img, M, (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )

        # --- Crop ---
        has_crop = top > 0.001 or bottom < 0.999 or left > 0.001 or right < 0.999
        if has_crop:
            y1 = int(top * h)
            y2 = int(bottom * h)
            x1 = int(left * w)
            x2 = int(right * w)
            # Ensure minimum 1px
            y2 = max(y1 + 1, y2)
            x2 = max(x1 + 1, x2)
            img = img[y1:y2, x1:x2].copy()

        buf.data = img
        buf.metadata["width"] = img.shape[1]
        buf.metadata["height"] = img.shape[0]
        return buf
