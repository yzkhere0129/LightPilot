"""Output module: final clipping and file export.

By the time data reaches this module, it should already be in
gamma-encoded sRGB (from tone_curve). This module clips, converts
to integer, and writes to disk.

Supported formats: JPEG, TIFF (16-bit), PNG (16-bit).

Note: Uses cv2.imencode + Path.write_bytes instead of cv2.imwrite
      to support Unicode file paths on Windows (e.g. Chinese usernames).
"""

from __future__ import annotations

import numpy as np
import cv2
from pathlib import Path

from .base import BaseModule
from ..buffer import ImageBuffer


def _cv_save(path: Path, img: np.ndarray, params: list | None = None) -> None:
    """cv2.imwrite replacement that handles Unicode paths on Windows."""
    ext = path.suffix
    if params:
        ok, buf = cv2.imencode(ext, img, params)
    else:
        ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise IOError(f"Failed to encode image: {path}")
    path.write_bytes(buf.tobytes())


class OutputModule(BaseModule):

    @property
    def name(self) -> str:
        return "output"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        """Final clip to [0, 1].  No spatial transform here."""
        buf.data = np.clip(buf.data, 0, 1).astype(np.float32)
        return buf

    @staticmethod
    def save(buf: ImageBuffer, output_path: str, quality: int = 95) -> None:
        """Write the processed buffer to a file.

        Args:
            buf: Processed ImageBuffer (gamma-encoded sRGB float32).
            output_path: Destination file path.
            quality: JPEG quality 1-100 (ignored for TIFF/PNG).
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()

        if suffix in (".jpg", ".jpeg"):
            out = np.clip(buf.data * 255.0, 0, 255).astype(np.uint8)
            out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
            _cv_save(path, out_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])

        elif suffix in (".tiff", ".tif"):
            out = np.clip(buf.data * 65535.0, 0, 65535).astype(np.uint16)
            out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
            _cv_save(path, out_bgr)

        elif suffix == ".png":
            out = np.clip(buf.data * 65535.0, 0, 65535).astype(np.uint16)
            out_bgr = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
            _cv_save(path, out_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 3])

        else:
            raise ValueError(f"Unsupported output format: {suffix}")
