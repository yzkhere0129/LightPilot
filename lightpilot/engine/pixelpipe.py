"""PixelPipe — ordered pipeline orchestrator.

Executes processing modules in a fixed order on an ImageBuffer.
Supports proxy resolution for fast preview and full-res for export.

Performance optimizations:
- RAW decode result is cached (saves ~1200ms per re-render).
- Module-level caching: only re-runs from the first changed module onward.
"""

from __future__ import annotations

import time

from ..engine.buffer import ImageBuffer
from .modules.raw_decode import RawDecodeModule
from .modules.white_balance import WhiteBalanceModule
from .modules.exposure import ExposureModule
from .modules.tone_curve import ToneCurveModule
from .modules.hsl import HslModule
from .modules.color_grading import ColorGradingModule
from .modules.detail import DetailModule
from .modules.effects import EffectsModule
from .modules.crop import CropModule
from .modules.output import OutputModule

# Maps parameter names → module index so we know where to restart the pipeline
# when a specific parameter changes.
_MODULE_INDEX = {
    # 0: raw_decode (no user params)
    # 1: white_balance
    "Temperature": 1, "Tint": 1,
    # 2: exposure
    "Exposure2012": 2, "Blacks2012": 2, "Whites2012": 2,
    # 3: tone_curve
    "Contrast2012": 3, "Highlights2012": 3, "Shadows2012": 3,
}
# 4: hsl (accept both HueAdjustmentRed and HueAdjustRed)
for _axis in ("HueAdjust", "SaturationAdjust", "LuminanceAdjust",
              "HueAdjustment", "SaturationAdjustment", "LuminanceAdjustment"):
    for _ch in ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta"):
        _MODULE_INDEX[f"{_axis}{_ch}"] = 4
_MODULE_INDEX["Vibrance"] = 4
_MODULE_INDEX["Saturation"] = 4
# 5: color_grading
for _prefix in ("SplitToningShadow", "SplitToningHighlight", "SplitToningBalance",
                 "ColorGradeShadow", "ColorGradeMidtone", "ColorGradeHighlight",
                 "ColorGradeGlobal", "ColorGradeBlending", "ColorGradeBalance"):
    for _suffix in ("Hue", "Sat", "Lum", "Saturation", ""):
        _MODULE_INDEX[f"{_prefix}{_suffix}"] = 5
# 6: detail
for _p in ("Sharpness", "SharpenRadius", "SharpenDetail", "SharpenEdgeMasking",
           "LuminanceSmoothing", "LuminanceNoiseReductionDetail",
           "LuminanceNoiseReductionContrast", "ColorNoiseReduction",
           "ColorNoiseReductionDetail", "ColorNoiseReductionSmoothness",
           "Clarity2012", "Texture", "Dehaze"):
    _MODULE_INDEX[_p] = 6
# 7: effects
for _p in ("PostCropVignetteAmount", "PostCropVignetteMidpoint",
           "PostCropVignetteFeather", "PostCropVignetteRoundness",
           "PostCropVignetteHighlightContrast",
           "GrainAmount", "GrainSize", "GrainFrequency"):
    _MODULE_INDEX[_p] = 7
# 8: crop
for _p in ("CropAngle", "CropTop", "CropBottom", "CropLeft", "CropRight"):
    _MODULE_INDEX[_p] = 8


class PixelPipe:
    """Executes the image processing pipeline with caching."""

    def __init__(self, proxy_pixels: int = 2_000_000):
        self.proxy_pixels = proxy_pixels
        self.modules = [
            RawDecodeModule(),      # 0
            WhiteBalanceModule(),   # 1
            ExposureModule(),       # 2
            ToneCurveModule(),      # 3
            HslModule(),            # 4
            ColorGradingModule(),   # 5
            DetailModule(),         # 6
            EffectsModule(),        # 7
            CropModule(),           # 8
            OutputModule(),         # 9
        ]
        # --- Caches ---
        self._cache_source: str | None = None
        self._cache_proxy: int = 0
        # Per-module output cache (after each module)
        self._module_cache: list[ImageBuffer | None] = [None] * len(self.modules)
        # Last params used for rendering
        self._last_params: dict | None = None

    def clear_cache(self) -> None:
        """Invalidate all caches (call when switching source files)."""
        self._cache_source = None
        self._module_cache = [None] * len(self.modules)
        self._last_params = None

    def _find_start_module(self, params: dict) -> int:
        """Determine the earliest module that needs re-running."""
        if self._last_params is None:
            return 0  # first render, run everything

        # Find earliest module whose relevant params changed
        earliest = len(self.modules)
        for key, value in params.items():
            if key.startswith("_"):
                continue
            old = self._last_params.get(key)
            if old is None and value == 0:
                continue
            if old != value:
                idx = _MODULE_INDEX.get(key, 1)  # unknown params → start from WB
                earliest = min(earliest, idx)

        # Also check if any old params were removed
        for key, old_value in self._last_params.items():
            if key.startswith("_"):
                continue
            if key not in params:
                idx = _MODULE_INDEX.get(key, 1)
                earliest = min(earliest, idx)

        return earliest

    def process(
        self,
        source_path: str,
        params: dict | None = None,
        verbose: bool = False,
    ) -> ImageBuffer:
        if params is None:
            params = {}
        params["_proxy_pixels"] = self.proxy_pixels

        # Check if source changed → full invalidation
        cache_key_match = (
            self._cache_source == source_path
            and self._cache_proxy == self.proxy_pixels
        )
        if not cache_key_match:
            self.clear_cache()
            self._cache_source = source_path
            self._cache_proxy = self.proxy_pixels

        # Determine where to start
        if self._module_cache[0] is None:
            start = 0  # no decode cache, run from beginning
        else:
            start = self._find_start_module(params)

        if start >= len(self.modules) and self._module_cache[-1] is not None:
            # Nothing changed, return last result
            if verbose:
                print("  (all cached, no changes)")
            return self._module_cache[-1].clone()

        # Get starting buffer
        if start == 0:
            buf = ImageBuffer(metadata={"source_path": source_path})
        else:
            buf = self._module_cache[start - 1].clone()

        # Run modules from start onward
        for i in range(start, len(self.modules)):
            module = self.modules[i]
            t0 = time.perf_counter()
            buf = module.process(buf, params)
            dt = (time.perf_counter() - t0) * 1000
            if verbose:
                print(f"  [{module.name:16s}] {dt:7.1f} ms")
            # Cache this module's output (clone to avoid mutation by downstream)
            if i < len(self.modules) - 1:
                self._module_cache[i] = buf.clone()
            else:
                self._module_cache[i] = buf  # last module, no downstream

        # Invalidate downstream caches that weren't re-run (shouldn't happen, but safe)
        self._last_params = {k: v for k, v in params.items() if not k.startswith("_")}
        return buf

    def process_and_save(
        self,
        source_path: str,
        output_path: str,
        params: dict | None = None,
        quality: int = 95,
        verbose: bool = False,
    ) -> ImageBuffer:
        buf = self.process(source_path, params, verbose=verbose)

        t0 = time.perf_counter()
        OutputModule.save(buf, output_path, quality)
        dt = (time.perf_counter() - t0) * 1000
        if verbose:
            print(f"  [{'save':16s}] {dt:7.1f} ms")

        return buf
