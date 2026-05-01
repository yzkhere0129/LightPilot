"""PipelineBridge — replaces LRBridge for standalone operation.

Instead of communicating with Lightroom via file-system IPC, this bridge
talks directly to the PixelPipe engine. It fulfills the same interface
that the agent expects:
  - request_export() → render preview and return (settings, preview_path)
  - send_adjustments() → apply parameter deltas to current settings
  - get_current_settings() → return current parameter dict
  - reset() → clear state
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

from ..engine.pixelpipe import PixelPipe
from ..engine.modules.output import OutputModule
from ..catalog.sidecar import load as load_sidecar, save as save_sidecar

log = logging.getLogger(__name__)


class PipelineBridge:
    """Direct bridge to the PixelPipe engine (no LR dependency)."""

    def __init__(
        self,
        source_path: str | Path,
        proxy_pixels: int = 2_000_000,
        preview_dir: str | Path | None = None,
    ):
        """
        Args:
            source_path: Path to the RAW or image file.
            proxy_pixels: Proxy resolution for previews.
            preview_dir: Directory for temporary preview files.
                         Defaults to system temp dir.
        """
        self.source_path = Path(source_path)
        self.proxy_pixels = proxy_pixels
        self.pipe = PixelPipe(proxy_pixels=proxy_pixels)
        if preview_dir:
            self.preview_dir = Path(preview_dir)
        else:
            # Use project-local temp dir to avoid Unicode issues on Windows
            # (e.g. Chinese username in C:\Users\...)
            local_tmp = Path(__file__).resolve().parents[2] / ".tmp" / "previews"
            local_tmp.mkdir(parents=True, exist_ok=True)
            self.preview_dir = local_tmp
        self.preview_dir.mkdir(parents=True, exist_ok=True)

        # Current editing parameters
        self._settings: dict = {}
        self._preview_counter = 0

    def reset(self) -> None:
        """Clear current settings (start fresh)."""
        self._settings = {}
        self._preview_counter = 0
        log.info("PipelineBridge reset")

    def request_export(self) -> tuple[dict, Path]:
        """Render the image with current settings and return preview path.

        Returns:
            (current_settings_dict, preview_jpeg_path)
        """
        # Render through the pipeline
        buf = self.pipe.process(str(self.source_path), self._settings.copy())

        # Save preview JPEG
        self._preview_counter += 1
        preview_path = self.preview_dir / f"preview_{self._preview_counter:03d}.jpg"
        OutputModule.save(buf, str(preview_path), quality=90)

        log.info("Exported preview %s (%dx%d)", preview_path.name, buf.width, buf.height)
        return self._settings.copy(), preview_path

    # Valid parameter ranges for clamping (subset of most common params)
    _CLAMP = {
        "Exposure2012": (-5.0, 5.0),
        "Contrast2012": (-100, 100), "Highlights2012": (-100, 100),
        "Shadows2012": (-100, 100), "Whites2012": (-100, 100),
        "Blacks2012": (-100, 100), "Texture": (-100, 100),
        "Clarity2012": (-100, 100), "Dehaze": (-100, 100),
        "Vibrance": (-100, 100), "Saturation": (-100, 100),
        "Temperature": (2000, 50000), "Tint": (-150, 150),
        "Sharpness": (0, 150), "LuminanceSmoothing": (0, 100),
        "ColorNoiseReduction": (0, 100),
        "PostCropVignetteAmount": (-100, 100),
        "GrainAmount": (0, 100), "GrainSize": (0, 100),
    }

    def send_adjustments(self, adjustments: dict) -> None:
        """Apply parameter adjustments as ABSOLUTE target values.

        Args:
            adjustments: Dict of parameter name → absolute target value.
        """
        for key, value in adjustments.items():
            # Clamp to valid range if known
            if key in self._CLAMP:
                lo, hi = self._CLAMP[key]
                value = max(lo, min(hi, value))
            self._settings[key] = value

        log.info("Applied %d adjustments: %s",
                 len(adjustments), list(adjustments.keys()))

    def get_current_settings(self) -> Optional[dict]:
        """Return current settings dict."""
        return self._settings.copy()

    def save_to_sidecar(self) -> None:
        """Persist current settings to a sidecar JSON file."""
        if self._settings:
            save_sidecar(self.source_path, self._settings)
            log.info("Saved %d params to sidecar", len(self._settings))

    def load_from_sidecar(self) -> dict:
        """Load previously saved settings from sidecar."""
        self._settings = load_sidecar(self.source_path)
        log.info("Loaded %d params from sidecar", len(self._settings))
        return self._settings.copy()

    def export_full_resolution(self, output_path: str, quality: int = 95) -> None:
        """Re-render at full resolution and save."""
        full_pipe = PixelPipe(proxy_pixels=0)
        buf = full_pipe.process(str(self.source_path), self._settings.copy())
        OutputModule.save(buf, output_path, quality)
        log.info("Full-res export: %s (%dx%d)", output_path, buf.width, buf.height)
