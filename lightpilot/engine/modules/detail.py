"""Detail module: sharpening + noise reduction + Clarity/Texture/Dehaze.

Operates in gamma-encoded sRGB space.

- Sharpening: Unsharp-mask approach.
- Noise reduction (luminance): Gaussian blur blend.
- Clarity: CLAHE-based local contrast.
- Texture: High-frequency detail enhancement (frequency separation).
- Dehaze: Dark channel prior based dehazing.
"""

from __future__ import annotations

import numpy as np
import cv2

from .base import BaseModule
from ..buffer import ImageBuffer


class DetailModule(BaseModule):

    @property
    def name(self) -> str:
        return "detail"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        sharpen = params.get("Sharpness", 0)         # 0..150
        nr_lum = params.get("LuminanceSmoothing", 0)  # 0..100
        clarity = params.get("Clarity2012", 0)        # -100..+100
        texture = params.get("Texture", 0)            # -100..+100
        dehaze = params.get("Dehaze", 0)              # -100..+100

        img = buf.data

        # --- Noise reduction (luminance) ---
        if nr_lum > 1:
            img = self._denoise(img, nr_lum)

        # --- Sharpening (unsharp mask) ---
        if sharpen > 1:
            img = self._sharpen(img, sharpen)

        # --- Clarity (local contrast via CLAHE) ---
        if abs(clarity) > 1:
            img = self._clarity(img, clarity)

        # --- Texture (high-frequency enhancement) ---
        if abs(texture) > 1:
            img = self._texture(img, texture)

        # --- Dehaze (dark channel prior) ---
        if abs(dehaze) > 1:
            img = self._dehaze(img, dehaze)

        buf.data = np.clip(img, 0, 1).astype(np.float32)
        return buf

    @staticmethod
    def _denoise(img: np.ndarray, strength: float) -> np.ndarray:
        """Simple luminance noise reduction via Gaussian blur blend."""
        sigma = strength / 100.0 * 3.0  # max sigma ~3px
        ksize = int(sigma * 4) | 1  # odd kernel
        ksize = max(3, min(ksize, 15))
        blurred = cv2.GaussianBlur(img, (ksize, ksize), sigma)
        alpha = strength / 100.0 * 0.7  # blend factor
        return img * (1 - alpha) + blurred * alpha

    @staticmethod
    def _sharpen(img: np.ndarray, amount: float) -> np.ndarray:
        """Unsharp mask sharpening."""
        sigma = 1.0
        blurred = cv2.GaussianBlur(img, (0, 0), sigma)
        strength = amount / 150.0 * 1.5  # max 1.5x
        return img + (img - blurred) * strength

    @staticmethod
    def _clarity(img: np.ndarray, amount: float) -> np.ndarray:
        """Local contrast enhancement using CLAHE on luminance channel."""
        # Convert to LAB for luminance-only processing
        img_8 = np.clip(img * 255, 0, 255).astype(np.uint8)
        lab = cv2.cvtColor(img_8, cv2.COLOR_RGB2LAB)

        clip_limit = abs(amount) / 100.0 * 4.0 + 0.5
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        enhanced_l = clahe.apply(lab[:, :, 0])

        if amount > 0:
            # Blend toward enhanced
            alpha = amount / 100.0
        else:
            # Blend away from enhanced (soften)
            alpha = amount / 100.0  # negative → blend toward original

        l_new = lab[:, :, 0].astype(np.float32) + alpha * (
            enhanced_l.astype(np.float32) - lab[:, :, 0].astype(np.float32)
        )
        lab[:, :, 0] = np.clip(l_new, 0, 255).astype(np.uint8)
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        return result.astype(np.float32) / 255.0

    @staticmethod
    def _texture(img: np.ndarray, amount: float) -> np.ndarray:
        """High-frequency detail via frequency separation."""
        # Low-pass: larger kernel for texture band
        sigma = 5.0
        low = cv2.GaussianBlur(img, (0, 0), sigma)
        high = img - low
        strength = amount / 100.0 * 0.8
        return img + high * strength

    @staticmethod
    def _dehaze(img: np.ndarray, amount: float) -> np.ndarray:
        """Dark-channel-prior based dehazing."""
        if amount > 0:
            # Estimate atmospheric light from dark channel
            dark = np.min(img, axis=2)
            ksize = max(3, int(min(img.shape[0], img.shape[1]) * 0.01) | 1)
            dark_eroded = cv2.erode(dark, np.ones((ksize, ksize), np.uint8))

            # Atmospheric light: brightest pixel in dark channel
            flat = dark_eroded.flatten()
            top_idx = np.argpartition(flat, -100)[-100:]
            atm = np.mean(img.reshape(-1, 3)[top_idx], axis=0)
            atm = np.clip(atm, 0.1, 1.0)

            # Transmission
            norm = img / atm[np.newaxis, np.newaxis, :]
            t = 1.0 - (amount / 100.0 * 0.9) * np.min(norm, axis=2)
            t = np.clip(t, 0.1, 1.0)

            # Recover
            result = (img - atm[np.newaxis, np.newaxis, :]) / t[:, :, np.newaxis] + atm[np.newaxis, np.newaxis, :]
            return np.clip(result, 0, 1).astype(np.float32)
        else:
            # Negative dehaze: add haze effect
            strength = abs(amount) / 100.0 * 0.5
            haze = np.ones_like(img) * 0.7
            return img * (1 - strength) + haze * strength
