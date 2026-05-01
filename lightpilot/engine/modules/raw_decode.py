"""RAW decoding module using rawpy (LibRaw).

Supports all major RAW formats: CR2, CR3, ARW, NEF, DNG, RAF, ORF, RW2, PEF, SRW.
Falls back to OpenCV for standard image formats (JPEG, TIFF, PNG).
"""

from __future__ import annotations

import numpy as np
import cv2
from pathlib import Path

from .base import BaseModule
from ..buffer import ImageBuffer

RAW_EXTENSIONS = {
    ".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf",
    ".orf", ".rw2", ".pef", ".srw", ".x3f", ".iiq",
    ".3fr", ".rwl", ".raw",
}


class RawDecodeModule(BaseModule):

    @property
    def name(self) -> str:
        return "raw_decode"

    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        path = buf.metadata["source_path"]
        suffix = Path(path).suffix.lower()
        proxy_pixels = params.get("_proxy_pixels", 2_000_000)

        if suffix in RAW_EXTENSIONS:
            img, cam_wb = self._decode_raw(path)
        else:
            img, cam_wb = self._decode_standard(path)

        orig_h, orig_w = img.shape[:2]

        # Proxy resize for preview performance
        total = orig_h * orig_w
        if proxy_pixels and total > proxy_pixels:
            scale = (proxy_pixels / total) ** 0.5
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        buf.data = img
        buf.metadata.update({
            "width": img.shape[1],
            "height": img.shape[0],
            "original_width": orig_w,
            "original_height": orig_h,
            "camera_wb": cam_wb,
            "as_shot_temperature": 6500,
        })
        return buf

    @staticmethod
    def _decode_raw(path: str) -> tuple[np.ndarray, list[float]]:
        """Decode RAW file via rawpy → linear float32 sRGB."""
        import rawpy

        with rawpy.imread(path) as raw:
            rgb16 = raw.postprocess(
                output_color=rawpy.ColorSpace.sRGB,
                gamma=(1, 1),           # linear output
                no_auto_bright=True,
                output_bps=16,
                use_camera_wb=True,
            )
            try:
                cam_wb = [float(x) for x in raw.camera_whitebalance[:3]]
            except Exception:
                cam_wb = [1.0, 1.0, 1.0]

        img = rgb16.astype(np.float32) / 65535.0
        return img, cam_wb

    @staticmethod
    def _decode_standard(path: str) -> tuple[np.ndarray, list[float]]:
        """Decode JPEG/TIFF/PNG via OpenCV → linear float32 sRGB."""
        # Use imdecode to handle Unicode paths on Windows
        data = np.fromfile(path, dtype=np.uint8)
        bgr = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        if bgr is None:
            raise FileNotFoundError(f"Cannot read image: {path}")

        # Handle bit depth
        if bgr.dtype == np.uint16:
            img = bgr.astype(np.float32) / 65535.0
        elif bgr.dtype == np.uint8:
            img = bgr.astype(np.float32) / 255.0
        else:
            img = bgr.astype(np.float32)

        # BGR → RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Standard images are gamma-encoded; linearize for pipeline
        img = np.power(np.clip(img, 0, 1), 2.2)

        return img, [1.0, 1.0, 1.0]
