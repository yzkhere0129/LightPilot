"""Effects module: vignette and film grain.

Operates in gamma-encoded sRGB space.
"""

from __future__ import annotations

import numpy as np

from .base import BaseModule
from ..buffer import ImageBuffer


class EffectsModule(BaseModule):

    @property
    def name(self) -> str:
        return "effects"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        vignette = params.get("PostCropVignetteAmount", 0)  # -100..+100
        grain = params.get("GrainAmount", 0)                # 0..100
        grain_size = params.get("GrainSize", 25)            # 0..100

        img = buf.data

        # --- Vignette ---
        if abs(vignette) > 1:
            img = self._vignette(img, vignette)

        # --- Film grain ---
        if grain > 1:
            img = self._grain(img, grain, grain_size)

        buf.data = np.clip(img, 0, 1).astype(np.float32)
        return buf

    @staticmethod
    def _vignette(img: np.ndarray, amount: float) -> np.ndarray:
        """Radial vignette: darken (negative) or lighten (positive) edges."""
        h, w = img.shape[:2]
        cy, cx = h / 2.0, w / 2.0
        max_r = (cx ** 2 + cy ** 2) ** 0.5

        y, x = np.ogrid[:h, :w]
        r = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        r = r / max_r  # normalize to [0, 1]

        # Smooth falloff: r^2 cosine blend
        mask = r ** 2
        strength = amount / 100.0 * 0.6  # max ±60% darkening/brightening

        if amount < 0:
            # Darken edges
            factor = 1.0 + strength * mask  # strength is negative
        else:
            # Lighten edges (unusual but supported)
            factor = 1.0 + strength * mask

        return img * factor[:, :, np.newaxis]

    @staticmethod
    def _grain(img: np.ndarray, amount: float, size: float) -> np.ndarray:
        """Monochromatic film grain noise."""
        h, w = img.shape[:2]
        strength = amount / 100.0 * 0.08  # max 8% noise

        # Generate noise at reduced resolution for larger grain
        scale = max(1, int(size / 25.0 * 3))
        noise_h = max(1, h // scale)
        noise_w = max(1, w // scale)

        noise = np.random.randn(noise_h, noise_w).astype(np.float32)

        if scale > 1:
            import cv2
            noise = cv2.resize(noise, (w, h), interpolation=cv2.INTER_LINEAR)

        return img + noise[:, :, np.newaxis] * strength
