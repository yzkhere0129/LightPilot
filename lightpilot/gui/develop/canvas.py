"""Image display canvas with zoom and pan support."""

import numpy as np
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtGui import QImage, QPixmap, QPainter, QWheelEvent, QMouseEvent
from PySide6.QtCore import Qt, QPoint, QPointF, Signal


class ImageCanvas(QWidget):
    """Displays the processed image with zoom/pan and before/after comparison."""

    FIT = "fit"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: #1a1a1a;")

        self._pixmap: QPixmap | None = None
        self._zoom = 0.0  # 0 = fit-to-window
        self._pan_offset = QPointF(0, 0)
        self._last_mouse_pos: QPoint | None = None
        self._dragging = False

    def set_image(self, img: np.ndarray | None) -> None:
        """Update displayed image from float32 RGB [0,1] array."""
        if img is None:
            self._pixmap = None
            self.update()
            return

        h, w, _ = img.shape
        img8 = np.clip(img * 255, 0, 255).astype(np.uint8)
        # Create QImage from numpy (needs contiguous memory)
        img8 = np.ascontiguousarray(img8)
        qimg = QImage(img8.data, w, h, w * 3, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg.copy())  # copy to own data
        self._zoom = 0.0  # reset to fit
        self._pan_offset = QPointF(0, 0)
        self.update()

    def paintEvent(self, event):
        if self._pixmap is None:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        pw, ph = self._pixmap.width(), self._pixmap.height()
        cw, ch = self.width(), self.height()

        if self._zoom <= 0:
            # Fit to window
            scale = min(cw / pw, ch / ph)
        else:
            scale = self._zoom

        sw = pw * scale
        sh = ph * scale

        x = (cw - sw) / 2 + self._pan_offset.x()
        y = (ch - sh) / 2 + self._pan_offset.y()

        p.drawPixmap(
            int(x), int(y), int(sw), int(sh),
            self._pixmap,
        )
        p.end()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if self._zoom <= 0:
            pw, ph = self._pixmap.width(), self._pixmap.height()
            cw, ch = self.width(), self.height()
            self._zoom = min(cw / pw, ch / ph)

        if delta > 0:
            self._zoom *= 1.15
        else:
            self._zoom /= 1.15

        self._zoom = max(0.05, min(10.0, self._zoom))
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._last_mouse_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging and self._last_mouse_pos:
            delta = event.pos() - self._last_mouse_pos
            self._pan_offset += QPointF(delta.x(), delta.y())
            self._last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False
        self._last_mouse_pos = None

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double-click to reset zoom to fit."""
        self._zoom = 0.0
        self._pan_offset = QPointF(0, 0)
        self.update()
