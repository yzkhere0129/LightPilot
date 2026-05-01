"""Exposure, whites, and blacks adjustment module.

Operates on linear RGB data.
- Exposure2012: EV stops (-5 to +5), applied as 2^EV multiplier.
- Blacks2012:   Shadow floor (-100 to +100).
- Whites2012:   Highlight ceiling (-100 to +100).
"""

from __future__ import annotations

import numpy as np

from .base import BaseModule
from ..buffer import ImageBuffer


class ExposureModule(BaseModule):

    @property
    def name(self) -> str:
        return "exposure"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        exposure = params.get("Exposure2012", 0.0)   # EV stops
        blacks = params.get("Blacks2012", 0)          # -100..+100
        whites = params.get("Whites2012", 0)          # -100..+100

        img = buf.data

        # --- Exposure: 2^EV gain ---
        if abs(exposure) > 0.001:
            img = img * (2.0 ** exposure)

        # --- Blacks: shift shadow floor ---
        # Positive = lift shadows (brighter), Negative = crush (darker)
        if abs(blacks) > 0.5:
            shift = blacks / 100.0 * 0.05  # max ±5% of range
            img = img + shift

        # --- Whites: scale highlight ceiling ---
        # Positive = extend highlights, Negative = pull down
        if abs(whites) > 0.5:
            scale = 1.0 / (1.0 - whites / 100.0 * 0.2)  # 0.8x – 1.25x
            img = img * scale

        # Don't clip here — let tone_curve handle range compression
        buf.data = img
        return buf
