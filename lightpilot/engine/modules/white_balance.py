"""White balance adjustment module.

Adjusts color temperature (Kelvin) and tint (green-magenta axis).
Operates on linear RGB data before tone mapping.
"""

from __future__ import annotations

import math
import numpy as np

from .base import BaseModule
from ..buffer import ImageBuffer


def _kelvin_to_rgb(kelvin: float) -> tuple[float, float, float]:
    """Approximate RGB ratios for a blackbody color temperature.

    Uses Tanner Helland's algorithm, normalized to [0, 1] range.
    Valid for ~1000K–40000K.
    """
    temp = max(1000, min(40000, kelvin)) / 100.0

    # Red
    if temp <= 66:
        r = 1.0
    else:
        r = 1.2929362 * ((temp - 60) ** -0.1332047592)

    # Green
    if temp <= 66:
        g = 0.39008158 * math.log(temp) - 0.63184144
    else:
        g = 1.1298909 * ((temp - 60) ** -0.0755148492)

    # Blue
    if temp >= 66:
        b = 1.0
    elif temp <= 19:
        b = 0.0
    else:
        b = 0.54320679 * math.log(temp - 10) - 1.19625409

    return (
        max(0.001, min(1.0, r)),
        max(0.001, min(1.0, g)),
        max(0.001, min(1.0, b)),
    )


class WhiteBalanceModule(BaseModule):

    @property
    def name(self) -> str:
        return "white_balance"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        target_temp = params.get("Temperature")
        tint = params.get("Tint", 0)
        as_shot = buf.metadata.get("as_shot_temperature", 6500)

        if target_temp is None:
            target_temp = as_shot

        # --- Color temperature adjustment ---
        if abs(target_temp - as_shot) > 1:
            src_r, src_g, src_b = _kelvin_to_rgb(as_shot)
            dst_r, dst_g, dst_b = _kelvin_to_rgb(target_temp)

            # Correction ratios, normalized so green ≈ 1
            r_gain = (dst_r / src_r)
            g_gain = (dst_g / src_g)
            b_gain = (dst_b / src_b)
            norm = g_gain
            gains = np.array(
                [r_gain / norm, 1.0, b_gain / norm], dtype=np.float32
            )
            buf.data *= gains[np.newaxis, np.newaxis, :]

        # --- Tint adjustment (green-magenta axis) ---
        # LR range: -150 to +150.  Positive = magenta, negative = green.
        if abs(tint) > 0.5:
            tint_gain = 1.0 - tint / 300.0  # +150→0.5×G, -150→1.5×G
            buf.data[:, :, 1] *= tint_gain

        return buf
