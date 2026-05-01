"""Main window: Library / Develop dual-module layout.

Rendering is performed in a dedicated background thread so the UI
never freezes, even during heavy processing.
"""

from pathlib import Path
import logging
import threading

import yaml
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QToolBar, QStatusBar, QScrollArea,
    QSplitter, QPushButton, QFileDialog, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QAction, QKeySequence

from ..engine.pixelpipe import PixelPipe
from ..engine.modules.output import OutputModule
from ..catalog.database import CatalogDB
from ..catalog.sidecar import load as load_sidecar, save as save_sidecar

from .library.library_view import LibraryView
from .develop.canvas import ImageCanvas
from .develop.histogram import HistogramWidget
from .develop.ai_panel import AiPanel
from .develop.panels.basic_panel import BasicPanel
from .develop.panels.tone_curve_panel import ToneCurvePanel
from .develop.panels.hsl_panel import HslPanel
from .develop.panels.color_grading_panel import ColorGradingPanel
from .develop.panels.detail_panel import DetailPanel
from .develop.panels.effects_panel import EffectsPanel
from .develop.panels.crop_panel import CropPanel

log = logging.getLogger(__name__)

# Interactive proxy: 1MP for snappy slider response.
# Export uses full resolution (proxy_pixels=0).
INTERACTIVE_PROXY = 1_000_000


class RenderThread(QThread):
    """Dedicated rendering thread.

    Accepts render requests via `request()`. If a new request arrives
    while a render is in progress, the current result is discarded and
    the new params are rendered instead.
    """

    resultReady = Signal(object)  # numpy float32 RGB array

    def __init__(self):
        super().__init__()
        self.pipe = PixelPipe(proxy_pixels=INTERACTIVE_PROXY)
        self._lock = threading.Lock()
        self._source: str | None = None
        self._params: dict | None = None
        self._event = threading.Event()
        self._stop_flag = False

    def request(self, source_path: str, params: dict) -> None:
        """Submit a new render request (thread-safe)."""
        with self._lock:
            self._source = source_path
            self._params = params.copy()
        self._event.set()

    def stop(self) -> None:
        self._stop_flag = True
        self._event.set()
        self.wait()

    def run(self) -> None:
        while not self._stop_flag:
            self._event.wait()
            self._event.clear()

            if self._stop_flag:
                break

            with self._lock:
                source = self._source
                params = self._params

            if source is None:
                continue

            try:
                buf = self.pipe.process(source, params)

                # If a newer request arrived during render, discard this result
                if self._event.is_set():
                    continue

                self.resultReady.emit(buf.data.copy())
            except Exception:
                log.exception("Render error")


class MainWindow(QMainWindow):
    """LightPilot main application window."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.setWindowTitle("LightPilot")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 1000)

        # State
        self._current_path: str | None = None
        self._current_params: dict = {}
        self._current_image: np.ndarray | None = None

        # Debounce timer — coalesces rapid slider changes
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(60)  # ms
        self._render_timer.timeout.connect(self._submit_render)

        # Background render thread
        self._render_thread = RenderThread()
        self._render_thread.resultReady.connect(self._on_render_done)
        self._render_thread.start()

        # Undo / Redo
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._undo_dirty = False  # True = undo snapshot taken for current drag

        # Catalog — use project-local path to avoid C: drive
        catalog_path = Path(__file__).resolve().parents[2] / ".data" / "catalog.db"
        self.catalog = CatalogDB(catalog_path)

        self._setup_ui()
        self._setup_actions()
        self._apply_theme()

    # ── UI Setup ──────────────────────────────────────────────

    def _setup_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # --- Library ---
        self.library_view = LibraryView(self.catalog)
        self.library_view.photoSelected.connect(self._open_in_develop)
        self.stack.addWidget(self.library_view)

        # --- Develop ---
        develop_widget = QWidget()
        develop_layout = QHBoxLayout(develop_widget)
        develop_layout.setContentsMargins(0, 0, 0, 0)
        develop_layout.setSpacing(0)

        # Center: canvas + histogram
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self.histogram = HistogramWidget()
        center_layout.addWidget(self.histogram)

        self.canvas = ImageCanvas()
        center_layout.addWidget(self.canvas, 1)

        develop_layout.addWidget(center, 1)

        # Right: panels scroll area
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFixedWidth(320)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setStyleSheet(
            "QScrollArea { background: #2a2a2a; border: none; }"
            "QScrollBar:vertical { background: #2a2a2a; width: 8px; }"
            "QScrollBar::handle:vertical { background: #555; border-radius: 4px; }"
        )

        panel_container = QWidget()
        panel_layout = QVBoxLayout(panel_container)
        panel_layout.setContentsMargins(4, 4, 4, 4)
        panel_layout.setSpacing(2)

        self.panels = []
        self.basic_panel = BasicPanel()
        self.tone_curve_panel = ToneCurvePanel()
        self.hsl_panel = HslPanel()
        self.color_grading_panel = ColorGradingPanel()
        self.detail_panel = DetailPanel()
        self.effects_panel = EffectsPanel()
        self.crop_panel = CropPanel()
        self.ai_panel = AiPanel()
        self.ai_panel.set_config(self.config)

        for panel in [
            self.ai_panel,
            self.basic_panel,
            self.tone_curve_panel,
            self.hsl_panel,
            self.color_grading_panel,
            self.detail_panel,
            self.effects_panel,
            self.crop_panel,
        ]:
            panel_layout.addWidget(panel)
            self.panels.append(panel)
            if hasattr(panel, "paramChanged"):
                panel.paramChanged.connect(self._on_param_changed)

        self.ai_panel.applySettings.connect(self._apply_ai_settings)

        panel_layout.addStretch()
        right_scroll.setWidget(panel_container)
        develop_layout.addWidget(right_scroll)

        self.stack.addWidget(develop_widget)

        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setStyleSheet(
            "QToolBar { background: #1e1e1e; border-bottom: 1px solid #333; spacing: 8px; }"
            "QToolButton { color: #ccc; padding: 6px 12px; }"
            "QToolButton:checked { color: #fff; background: #2563eb; border-radius: 3px; }"
        )
        self.addToolBar(toolbar)

        self.lib_btn = QPushButton("Library")
        self.lib_btn.setCheckable(True)
        self.lib_btn.setChecked(True)
        self.lib_btn.clicked.connect(lambda: self._switch_module(0))
        toolbar.addWidget(self.lib_btn)

        self.dev_btn = QPushButton("Develop")
        self.dev_btn.setCheckable(True)
        self.dev_btn.clicked.connect(lambda: self._switch_module(1))
        toolbar.addWidget(self.dev_btn)

        toolbar.addSeparator()

        open_btn = QPushButton("Open File")
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export)
        toolbar.addWidget(export_btn)

        self.statusBar().showMessage("Ready")

    def _setup_actions(self):
        undo = QAction("Undo", self)
        undo.setShortcut(QKeySequence.Undo)
        undo.triggered.connect(self._undo)
        self.addAction(undo)

        redo = QAction("Redo", self)
        redo.setShortcut(QKeySequence.Redo)
        redo.triggered.connect(self._redo)
        self.addAction(redo)

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e1e; }
            QWidget { color: #ccc; font-size: 12px; }
            QLabel { color: #ccc; }
            QPushButton {
                background: #333; color: #ccc; border: 1px solid #444;
                padding: 4px 10px; border-radius: 3px;
            }
            QPushButton:hover { background: #444; }
            QPushButton:pressed { background: #555; }
            QPushButton:checked { background: #2563eb; color: #fff; }
            QComboBox { background: #333; color: #ccc; border: 1px solid #444; padding: 3px; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView { background: #333; color: #ccc; }
            QSlider::groove:horizontal {
                background: #444; height: 4px; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ccc; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }
            QSlider::handle:horizontal:hover { background: #fff; }
            QStatusBar { background: #1a1a1a; color: #888; }
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab {
                background: #333; color: #aaa; padding: 4px 10px;
                border: 1px solid #444; border-bottom: none;
            }
            QTabBar::tab:selected { background: #2a2a2a; color: #fff; }
        """)

    # ── Navigation ────────────────────────────────────────────

    def _switch_module(self, index: int):
        self.stack.setCurrentIndex(index)
        self.lib_btn.setChecked(index == 0)
        self.dev_btn.setChecked(index == 1)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Images (*.arw *.cr2 *.cr3 *.nef *.dng *.raf *.orf *.rw2 *.pef *.srw "
            "*.jpg *.jpeg *.tiff *.tif *.png);;All Files (*)",
        )
        if path:
            self._open_in_develop(path)

    def _open_in_develop(self, path: str):
        self._current_path = path
        self._current_params = load_sidecar(path)
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._undo_dirty = False

        # Clear render caches for new file
        self._render_thread.pipe.clear_cache()

        for panel in self.panels:
            if hasattr(panel, "set_params"):
                panel.set_params(self._current_params)

        self.ai_panel.set_source(path)
        self._switch_module(1)
        self.statusBar().showMessage(f"Loading: {Path(path).name}...")
        self._submit_render()

    # ── Rendering (async in background thread) ────────────────

    def _on_param_changed(self, param_name: str, value: float):
        if self._current_path is None:
            return

        # Save undo snapshot once per drag gesture
        if not self._undo_dirty:
            self._undo_stack.append(self._current_params.copy())
            if len(self._undo_stack) > 100:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
            self._undo_dirty = True

        self._current_params[param_name] = value
        self._render_timer.start()  # debounce

    def _submit_render(self):
        """Send current params to the render thread."""
        self._undo_dirty = False  # next slider touch starts a new undo group
        if self._current_path:
            self._render_thread.request(self._current_path, self._current_params)

    def _on_render_done(self, image_data: np.ndarray):
        """Called in the main thread when the render thread finishes."""
        self._current_image = image_data
        self.canvas.set_image(image_data)
        self.histogram.update_image(image_data)
        h, w = image_data.shape[:2]
        name = Path(self._current_path).name if self._current_path else "?"
        self.statusBar().showMessage(f"{name} | {w}x{h}")

    # ── AI integration ────────────────────────────────────────

    def _apply_ai_settings(self, settings: dict):
        self._undo_stack.append(self._current_params.copy())
        self._redo_stack.clear()
        self._current_params.update(settings)
        for panel in self.panels:
            if hasattr(panel, "set_params"):
                panel.set_params(self._current_params)
        self._submit_render()
        self.statusBar().showMessage("AI settings applied")

    # ── Export ─────────────────────────────────────────────────

    def _export(self):
        if self._current_path is None:
            QMessageBox.warning(self, "Export", "No image loaded.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Image",
            str(Path(self._current_path).with_suffix(".jpg")),
            "JPEG (*.jpg);;TIFF (*.tiff);;PNG (*.png)",
        )
        if not path:
            return

        self.statusBar().showMessage("Exporting full resolution...")
        try:
            full_pipe = PixelPipe(proxy_pixels=0)
            buf = full_pipe.process(self._current_path, self._current_params.copy())
            OutputModule.save(buf, path, quality=95)
            save_sidecar(self._current_path, self._current_params)
            self.statusBar().showMessage(f"Exported: {path} ({buf.width}x{buf.height})")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    # ── Undo / Redo ───────────────────────────────────────────

    def _undo(self):
        if self._undo_stack:
            self._redo_stack.append(self._current_params.copy())
            self._current_params = self._undo_stack.pop()
            for panel in self.panels:
                if hasattr(panel, "set_params"):
                    panel.set_params(self._current_params)
            self._submit_render()

    def _redo(self):
        if self._redo_stack:
            self._undo_stack.append(self._current_params.copy())
            self._current_params = self._redo_stack.pop()
            for panel in self.panels:
                if hasattr(panel, "set_params"):
                    panel.set_params(self._current_params)
            self._submit_render()

    # ── Cleanup ───────────────────────────────────────────────

    def closeEvent(self, event):
        if self._current_path and self._current_params:
            save_sidecar(self._current_path, self._current_params)
        self._render_thread.stop()
        self.catalog.close()
        event.accept()
