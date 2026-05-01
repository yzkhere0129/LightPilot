"""QApplication entry point for LightPilot GUI."""

import sys
import logging
from pathlib import Path

import yaml
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from .main_window import MainWindow


def run_gui():
    """Launch the LightPilot GUI application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    app = QApplication(sys.argv)
    app.setApplicationName("LightPilot")
    app.setOrganizationName("LightPilot")

    # High-DPI support
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = MainWindow(config)
    window.show()

    # If a file was passed as argument, open it directly
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if Path(path).exists():
            window._open_in_develop(path)

    sys.exit(app.exec())
