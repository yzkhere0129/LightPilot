"""HSL / Color Mixer panel with 8-channel Hue/Saturation/Luminance sliders."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTabWidget, QScrollArea,
)
from PySide6.QtCore import Signal

from ...common.slider import ParamSlider

CHANNELS = ["Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta"]


class HslPanel(QWidget):
    paramChanged = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)

        header = QLabel("HSL / Color")
        header.setStyleSheet("color: #fff; font-weight: bold; font-size: 13px; padding: 4px 0;")
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { padding: 4px 8px; }")
        self.sliders: dict[str, ParamSlider] = {}

        for axis, prefix in [("Hue", "HueAdjustment"), ("Saturation", "SaturationAdjustment"), ("Luminance", "LuminanceAdjustment")]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(2, 2, 2, 2)
            tab_layout.setSpacing(1)
            for ch in CHANNELS:
                name = f"{prefix}{ch}"
                slider = ParamSlider(name, ch, -100, 100, 0, 1, 0)
                slider.valueChanged.connect(self.paramChanged.emit)
                tab_layout.addWidget(slider)
                self.sliders[name] = slider
            tab_layout.addStretch()
            tabs.addTab(tab, axis)

        layout.addWidget(tabs)

    def set_params(self, params: dict) -> None:
        for name, slider in self.sliders.items():
            if name in params:
                slider.set_value(params[name], emit=False)

    def get_params(self) -> dict:
        return {name: slider.value() for name, slider in self.sliders.items()}
