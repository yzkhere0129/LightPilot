"""Tone curve module: gamma mapping, contrast, highlights, and shadows.

Converts from linear RGB to gamma-encoded sRGB-like space, then applies
perceptual adjustments (contrast S-curve, highlight recovery, shadow lift).
"""

from __future__ import annotations

import numpy as np

from .base import BaseModule
from ..buffer import ImageBuffer

# sRGB gamma: 2.2 power approximation (exact sRGB is piecewise, but
# the difference is <1% and indistinguishable in practice for Phase 0).
GAMMA = 1.0 / 2.2


class ToneCurveModule(BaseModule):

    @property
    def name(self) -> str:
        return "tone_curve"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        contrast = params.get("Contrast2012", 0)       # -100..+100
        highlights = params.get("Highlights2012", 0)    # -100..+100
        shadows = params.get("Shadows2012", 0)          # -100..+100

        img = buf.data

        # --- Linear → perceptual (gamma encode) ---
        img = np.clip(img, 0, None)
        img = np.power(img, GAMMA)

        # --- Highlights recovery ---
        if abs(highlights) > 0.5:
            lum = self._luminance(img)
            # Smooth mask: ramps from 0 at mid to 1 at peak
            mask = np.clip((lum - 0.5) * 2.0, 0, 1)
            strength = highlights / 100.0 * 0.4

            if highlights < 0:
                # Pull down: compress highlights toward midtones
                img = img * (1.0 + strength * mask[:, :, np.newaxis])
            else:
                # Push up: expand toward white
                img = img + strength * mask[:, :, np.newaxis] * (1.0 - img)

        # --- Shadows lift/crush ---
        if abs(shadows) > 0.5:
            lum = self._luminance(img)
            # Mask: 1 in deep shadows, 0 at midtones+
            mask = np.clip(1.0 - lum * 2.0, 0, 1)
            strength = shadows / 100.0 * 0.4
            img = img + strength * mask[:, :, np.newaxis]

        # --- Contrast: S-curve around midpoint ---
        if abs(contrast) > 0.5:
            strength = contrast / 100.0 * 0.3
            midpoint = 0.5
            img = midpoint + (img - midpoint) * (1.0 + strength)

        buf.data = np.clip(img, 0, 1).astype(np.float32)
        return buf

    @staticmethod
    def _luminance(img: np.ndarray) -> np.ndarray:
        """Rec. 709 luminance from RGB."""
        return 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
