"""Library view: thumbnail grid with import and filtering."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QFileDialog,
    QAbstractItemView, QSplitter,
)
from PySide6.QtGui import QPixmap, QIcon, QImage
from PySide6.QtCore import Qt, Signal, QSize, QThread, QObject

import numpy as np


class ThumbnailLoader(QObject):
    """Background thumbnail generator."""
    thumbnailReady = Signal(str, QPixmap)  # file_path, thumbnail
    finished = Signal()

    def __init__(self, file_paths: list[str], size: int = 200):
        super().__init__()
        self.file_paths = file_paths
        self.size = size

    def run(self):
        for path in self.file_paths:
            try:
                pix = self._generate(path)
                if pix:
                    self.thumbnailReady.emit(path, pix)
            except Exception:
                pass
        self.finished.emit()

    def _generate(self, path: str) -> QPixmap | None:
        suffix = Path(path).suffix.lower()
        raw_exts = {".arw", ".cr2", ".cr3", ".nef", ".dng", ".raf", ".orf", ".rw2", ".pef", ".srw"}

        if suffix in raw_exts:
            try:
                import rawpy
                with rawpy.imread(path) as raw:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        pix = QPixmap()
                        pix.loadFromData(thumb.data)
                        return pix.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    elif thumb.format == rawpy.ThumbFormat.BITMAP:
                        h, w = thumb.data.shape[:2]
                        img = QImage(thumb.data.data, w, h, w * 3, QImage.Format_RGB888)
                        pix = QPixmap.fromImage(img)
                        return pix.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except Exception:
                pass
            return None
        else:
            pix = QPixmap(path)
            if pix.isNull():
                return None
            return pix.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class LibraryView(QWidget):
    """Thumbnail grid view for browsing imported photos."""

    photoSelected = Signal(str)  # file_path of selected photo

    def __init__(self, catalog_db, parent=None):
        super().__init__(parent)
        self.catalog = catalog_db
        self._thumb_thread: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar
        toolbar = QHBoxLayout()

        import_btn = QPushButton("Import Folder")
        import_btn.setStyleSheet(
            "background: #2563eb; color: #fff; font-weight: bold; "
            "padding: 6px 14px; border-radius: 4px;"
        )
        import_btn.clicked.connect(self._import_folder)
        toolbar.addWidget(import_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("Filter:"))
        self.rating_filter = QComboBox()
        self.rating_filter.addItems(["All", "1+", "2+", "3+", "4+", "5"])
        self.rating_filter.setStyleSheet("background: #333; color: #fff;")
        self.rating_filter.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(self.rating_filter)

        toolbar.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name", "Date", "Rating"])
        self.sort_combo.setStyleSheet("background: #333; color: #fff;")
        self.sort_combo.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(self.sort_combo)

        layout.addLayout(toolbar)

        # Thumbnail grid
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setIconSize(QSize(180, 180))
        self.grid.setSpacing(8)
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setSelectionMode(QAbstractItemView.SingleSelection)
        self.grid.setStyleSheet(
            "QListWidget { background: #222; border: none; }"
            "QListWidget::item { background: #333; border-radius: 4px; padding: 4px; }"
            "QListWidget::item:selected { background: #2563eb; }"
        )
        self.grid.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.grid)

        # Status bar
        self.status = QLabel("No photos imported")
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.status)

        self._refresh()

    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Import Folder")
        if folder:
            count = self.catalog.import_folder(folder)
            self.status.setText(f"Imported {count} photos from {Path(folder).name}")
            self._refresh()

    def _refresh(self):
        self.grid.clear()
        min_rating = self.rating_filter.currentIndex()
        sort_map = {"Name": "file_name", "Date": "capture_time", "Rating": "rating DESC"}
        order = sort_map.get(self.sort_combo.currentText(), "file_name")
        photos = self.catalog.get_photos(min_rating=min_rating, order_by=order)
        self.status.setText(f"{len(photos)} photos")

        paths = []
        for photo in photos:
            item = QListWidgetItem(photo["file_name"])
            item.setData(Qt.UserRole, photo["file_path"])
            item.setSizeHint(QSize(190, 210))
            self.grid.addItem(item)
            paths.append(photo["file_path"])

        # Load thumbnails in background
        if paths:
            self._load_thumbnails(paths)

    def _load_thumbnails(self, paths: list[str]):
        if self._thumb_thread and self._thumb_thread.isRunning():
            self._thumb_thread.quit()
            self._thumb_thread.wait()

        self._thumb_thread = QThread()
        self._loader = ThumbnailLoader(paths)
        self._loader.moveToThread(self._thumb_thread)
        self._thumb_thread.started.connect(self._loader.run)
        self._loader.thumbnailReady.connect(self._set_thumbnail)
        self._loader.finished.connect(self._thumb_thread.quit)
        self._thumb_thread.start()

    def _set_thumbnail(self, file_path: str, pixmap: QPixmap):
        for i in range(self.grid.count()):
            item = self.grid.item(i)
            if item.data(Qt.UserRole) == file_path:
                item.setIcon(QIcon(pixmap))
                break

    def _on_double_click(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)
        if path:
            self.photoSelected.emit(path)
