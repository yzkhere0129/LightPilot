"""Base class for all pipeline processing modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from ..buffer import ImageBuffer


class BaseModule(ABC):
    """Abstract base for a pixel-pipeline processing module.

    Each module reads/modifies an ImageBuffer in-place (or returns a new one).
    Modules are executed in a fixed order by PixelPipe.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique module identifier (e.g. 'exposure')."""
        ...

    @abstractmethod
    def process(self, buf: ImageBuffer, params: dict) -> ImageBuffer:
        """Process the image buffer.

        Args:
            buf: Current image buffer.
            params: Editing parameter dict from sidecar / user.
        Returns:
            The (possibly modified) ImageBuffer.
        """
        ...
