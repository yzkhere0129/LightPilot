"""HSL 8-channel adjustment module + global Vibrance/Saturation.

Adjusts Hue, Saturation, and Luminance for 8 color channels:
Red, Orange, Yellow, Green, Aqua, Blue, Purple, Magenta.

Also handles global Vibrance (selective saturation boost) and
Saturation (uniform saturation change).

Uses LR Classic parameter names (HueAdjustmentRed, etc.).
Operates in gamma-encoded sRGB space (after tone_curve).
"""

from __future__ import annotations

import numpy as np

from .base import BaseModule
from ..buffer import ImageBuffer

CHANNELS = ["Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta"]

# Hue center angles (degrees) and width for each channel
CHANNEL_HUES = {
    "Red":     (0,   30),
    "Orange":  (30,  30),
    "Yellow":  (60,  30),
    "Green":   (120, 40),
    "Aqua":    (180, 30),
    "Blue":    (240, 30),
    "Purple":  (280, 30),
    "Magenta": (320, 30),
}


def _rgb_to_hsl(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert RGB float32 [0,1] to HSL. Returns (H in [0,360], S in [0,1], L in [0,1])."""
    r, g, b = img[:, :, 0], img[:, :, 1], img[:, :, 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    L = (cmax + cmin) * 0.5

    S = np.zeros_like(L)
    mask = delta > 1e-7
    low = L <= 0.5
    S[mask & low] = delta[mask & low] / (2.0 * L[mask & low] + 1e-10)
    S[mask & ~low] = delta[mask & ~low] / (2.0 - 2.0 * L[mask & ~low] + 1e-10)

    H = np.zeros_like(L)
    rm = mask & (cmax == r)
    H[rm] = 60.0 * (((g[rm] - b[rm]) / (delta[rm] + 1e-10)) % 6)
    gm = mask & (cmax == g)
    H[gm] = 60.0 * (((b[gm] - r[gm]) / (delta[gm] + 1e-10)) + 2)
    bm = mask & (cmax == b)
    H[bm] = 60.0 * (((r[bm] - g[bm]) / (delta[bm] + 1e-10)) + 4)

    H = H % 360
    return H, S, L


def _hsl_to_rgb(H: np.ndarray, S: np.ndarray, L: np.ndarray) -> np.ndarray:
    """Convert HSL back to RGB float32 [0,1]."""
    C = (1.0 - np.abs(2.0 * L - 1.0)) * S
    H2 = H / 60.0
    X = C * (1.0 - np.abs(H2 % 2 - 1.0))
    m = L - C * 0.5

    r = np.zeros_like(L)
    g = np.zeros_like(L)
    b = np.zeros_like(L)

    for lo, hi, rv, gv, bv in [
        (0, 1, C, X, 0), (1, 2, X, C, 0), (2, 3, 0, C, X),
        (3, 4, 0, X, C), (4, 5, X, 0, C), (5, 6, C, 0, X),
    ]:
        mask = (H2 >= lo) & (H2 < hi)
        r[mask] = (rv[mask] if isinstance(rv, np.ndarray) else rv) + m[mask]
        g[mask] = (gv[mask] if isinstance(gv, np.ndarray) else gv) + m[mask]
        b[mask] = (bv[mask] if isinstance(bv, np.ndarray) else bv) + m[mask]

    mask = H2 >= 6
    r[mask] = C[mask] + m[mask]
    g[mask] = m[mask]
    b[mask] = m[mask]

    return np.stack([r, g, b], axis=-1).astype(np.float32)


def _channel_weight(hue: np.ndarray, center: float, width: float) -> np.ndarray:
    """Smooth weight mask for a hue channel (cosine falloff)."""
    d = np.abs(hue - center)
    d = np.minimum(d, 360 - d)
    w = np.clip(1.0 - d / width, 0, 1)
    return (np.cos((1.0 - w) * np.pi) + 1.0) * 0.5 * (w > 0).astype(np.float32)


def _get_hsl_param(params: dict, prefix: str, channel: str) -> float:
    """Get HSL param, accepting both 'HueAdjustmentRed' and 'HueAdjustRed' names."""
    val = params.get(f"{prefix}ment{channel}")  # HueAdjustmentRed
    if val is not None:
        return val
    return params.get(f"{prefix}{channel}", 0)  # HueAdjustRed (fallback)


class HslModule(BaseModule):

    @property
    def name(self) -> str:
        return "hsl"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        vibrance = params.get("Vibrance", 0)      # -100..+100
        saturation = params.get("Saturation", 0)   # -100..+100

        # Check if any HSL per-channel params are set
        has_hsl = False
        for ch in CHANNELS:
            for prefix in ("HueAdjust", "SaturationAdjust", "LuminanceAdjust"):
                if abs(_get_hsl_param(params, prefix, ch)) > 0.5:
                    has_hsl = True
                    break
            if has_hsl:
                break

        needs_hsl_convert = has_hsl or abs(vibrance) > 0.5 or abs(saturation) > 0.5

        if not needs_hsl_convert:
            return buf

        H, S, L = _rgb_to_hsl(buf.data)

        # --- Global Saturation ---
        if abs(saturation) > 0.5:
            factor = 1.0 + saturation / 100.0
            S = S * factor

        # --- Vibrance (selective: boosts low-saturation more) ---
        if abs(vibrance) > 0.5:
            strength = vibrance / 100.0
            # Weight: low saturation gets more boost, high saturation less
            weight = 1.0 - S  # 1.0 for unsaturated, 0.0 for fully saturated
            S = S + strength * weight * 0.6

        # --- Per-channel HSL ---
        if has_hsl:
            for ch_name in CHANNELS:
                center, width = CHANNEL_HUES[ch_name]
                hue_adj = _get_hsl_param(params, "HueAdjust", ch_name)
                sat_adj = _get_hsl_param(params, "SaturationAdjust", ch_name)
                lum_adj = _get_hsl_param(params, "LuminanceAdjust", ch_name)

                if abs(hue_adj) < 0.5 and abs(sat_adj) < 0.5 and abs(lum_adj) < 0.5:
                    continue

                cw = _channel_weight(H, center, width)

                if abs(hue_adj) > 0.5:
                    H = H + hue_adj * 0.3 * cw
                    H = H % 360

                if abs(sat_adj) > 0.5:
                    factor = 1.0 + sat_adj / 100.0
                    S = S * (1.0 + (factor - 1.0) * cw)

                if abs(lum_adj) > 0.5:
                    shift = lum_adj / 100.0 * 0.2
                    L = L + shift * cw

        S = np.clip(S, 0, 1)
        L = np.clip(L, 0, 1)

        buf.data = np.clip(_hsl_to_rgb(H, S, L), 0, 1)
        return buf
