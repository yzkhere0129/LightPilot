"""Color grading module (3-way: shadows, midtones, highlights).

Applies tinted color shifts to shadow/midtone/highlight regions,
similar to LR's Color Grading panel. Each region has hue + saturation.

Operates in gamma-encoded sRGB space.
"""

from __future__ import annotations

import math
import numpy as np

from .base import BaseModule
from ..buffer import ImageBuffer


def _hue_sat_to_rgb(hue: float, saturation: float) -> np.ndarray:
    """Convert a hue (0–360) and saturation (0–100) to an RGB tint vector."""
    if saturation < 0.5:
        return np.zeros(3, dtype=np.float32)

    h = hue / 60.0
    s = saturation / 100.0
    c = s
    x = c * (1 - abs(h % 2 - 1))

    if h < 1:
        rgb = [c, x, 0]
    elif h < 2:
        rgb = [x, c, 0]
    elif h < 3:
        rgb = [0, c, x]
    elif h < 4:
        rgb = [0, x, c]
    elif h < 5:
        rgb = [x, 0, c]
    else:
        rgb = [c, 0, x]

    return np.array(rgb, dtype=np.float32)


class ColorGradingModule(BaseModule):

    @property
    def name(self) -> str:
        return "color_grading"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        # Shadow tint
        sh_hue = params.get("SplitToningShadowHue", 0)
        sh_sat = params.get("SplitToningShadowSaturation", 0)
        # Highlight tint
        hi_hue = params.get("SplitToningHighlightHue", 0)
        hi_sat = params.get("SplitToningHighlightSaturation", 0)
        # Balance (-100..+100): negative = more shadows, positive = more highlights
        balance = params.get("SplitToningBalance", 0)
        # Color grade params (LR 2020+ style)
        cg_shadow_hue = params.get("ColorGradeShadowHue", sh_hue)
        cg_shadow_sat = params.get("ColorGradeShadowSat", sh_sat)
        cg_mid_hue = params.get("ColorGradeMidtoneHue", 0)
        cg_mid_sat = params.get("ColorGradeMidtoneSat", 0)
        cg_hi_hue = params.get("ColorGradeHighlightHue", hi_hue)
        cg_hi_sat = params.get("ColorGradeHighlightSat", hi_sat)

        has_any = (
            abs(cg_shadow_sat) > 0.5
            or abs(cg_mid_sat) > 0.5
            or abs(cg_hi_sat) > 0.5
        )
        if not has_any:
            return buf

        img = buf.data
        lum = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]

        # Compute per-pixel masks for shadow/mid/highlight
        split = 0.5 + balance / 200.0  # 0.0 – 1.0
        shadow_mask = np.clip(1.0 - lum / (split + 1e-6), 0, 1)
        highlight_mask = np.clip((lum - split) / (1.0 - split + 1e-6), 0, 1)
        midtone_mask = 1.0 - shadow_mask - highlight_mask
        midtone_mask = np.clip(midtone_mask, 0, 1)

        # Apply tints
        if abs(cg_shadow_sat) > 0.5:
            tint = _hue_sat_to_rgb(cg_shadow_hue, cg_shadow_sat)
            img = img + tint[np.newaxis, np.newaxis, :] * shadow_mask[:, :, np.newaxis] * 0.3

        if abs(cg_mid_sat) > 0.5:
            tint = _hue_sat_to_rgb(cg_mid_hue, cg_mid_sat)
            img = img + tint[np.newaxis, np.newaxis, :] * midtone_mask[:, :, np.newaxis] * 0.2

        if abs(cg_hi_sat) > 0.5:
            tint = _hue_sat_to_rgb(cg_hi_hue, cg_hi_sat)
            img = img + tint[np.newaxis, np.newaxis, :] * highlight_mask[:, :, np.newaxis] * 0.3

        buf.data = np.clip(img, 0, 1).astype(np.float32)
        return buf
