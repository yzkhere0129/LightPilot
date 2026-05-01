"""ImageBuffer — core data structure for the pixel pipeline."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImageBuffer:
    """Float32 RGB image buffer with metadata.

    Attributes:
        data: numpy array (H, W, 3), dtype float32, range [0, 1].
              Linear sRGB until tone_curve applies gamma.
        metadata: arbitrary dict for passing info between modules
                  (source_path, width, height, camera_wb, etc.).
    """

    data: np.ndarray | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def height(self) -> int:
        return self.data.shape[0] if self.data is not None else 0

    @property
    def width(self) -> int:
        return self.data.shape[1] if self.data is not None else 0

    @property
    def shape(self) -> tuple:
        return self.data.shape if self.data is not None else (0, 0, 0)

    def clone(self) -> ImageBuffer:
        """Deep copy of buffer and metadata."""
        return ImageBuffer(
            data=self.data.copy() if self.data is not None else None,
            metadata=self.metadata.copy(),
        )

    def to_8bit(self) -> np.ndarray:
        """Convert to uint8 [0, 255], clipping out-of-range values."""
        return np.clip(self.data * 255.0, 0, 255).astype(np.uint8)

    def to_16bit(self) -> np.ndarray:
        """Convert to uint16 [0, 65535]."""
        return np.clip(self.data * 65535.0, 0, 65535).astype(np.uint16)
