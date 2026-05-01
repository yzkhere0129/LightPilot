"""Real-time RGB histogram widget."""

import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath
from PySide6.QtCore import Qt


class HistogramWidget(QWidget):
    """Displays an RGB histogram overlay for the current image."""

    BINS = 256

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        self._hist_r = None
        self._hist_g = None
        self._hist_b = None

    def update_image(self, img: np.ndarray | None) -> None:
        """Compute histogram from float32 RGB image [0,1]."""
        if img is None:
            self._hist_r = self._hist_g = self._hist_b = None
            self.update()
            return

        img8 = np.clip(img * 255, 0, 255).astype(np.uint8)
        self._hist_r = np.bincount(img8[:, :, 0].ravel(), minlength=256).astype(np.float32)
        self._hist_g = np.bincount(img8[:, :, 1].ravel(), minlength=256).astype(np.float32)
        self._hist_b = np.bincount(img8[:, :, 2].ravel(), minlength=256).astype(np.float32)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(30, 30, 30))

        if self._hist_r is None:
            p.end()
            return

        w = self.width()
        h = self.height() - 4

        max_val = max(
            self._hist_r[1:-1].max(),
            self._hist_g[1:-1].max(),
            self._hist_b[1:-1].max(),
            1,
        )

        for hist, color in [
            (self._hist_r, QColor(220, 50, 50, 100)),
            (self._hist_g, QColor(50, 200, 50, 100)),
            (self._hist_b, QColor(50, 100, 220, 100)),
        ]:
            path = QPainterPath()
            path.moveTo(0, h + 2)
            for i in range(256):
                x = i / 255.0 * w
                y = h + 2 - (hist[i] / max_val * h)
                path.lineTo(x, y)
            path.lineTo(w, h + 2)
            path.closeSubpath()

            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawPath(path)

        p.end()
