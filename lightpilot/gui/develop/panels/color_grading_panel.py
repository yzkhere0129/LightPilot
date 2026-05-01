"""Color Grading panel: shadow/midtone/highlight hue+saturation."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget
from PySide6.QtCore import Signal

from ...common.slider import ParamSlider


class ColorGradingPanel(QWidget):
    paramChanged = Signal(str, float)

    REGIONS = [
        ("Shadow",    "ColorGradeShadow"),
        ("Midtone",   "ColorGradeMidtone"),
        ("Highlight",  "ColorGradeHighlight"),
        ("Global",    "ColorGradeGlobal"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)

        header = QLabel("Color Grading")
        header.setStyleSheet("color: #fff; font-weight: bold; font-size: 13px; padding: 4px 0;")
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { padding: 4px 6px; }")
        self.sliders: dict[str, ParamSlider] = {}

        for region_label, prefix in self.REGIONS:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(2, 2, 2, 2)
            tab_layout.setSpacing(1)

            for suffix, label, mn, mx, default in [
                ("Hue", "Hue", 0, 359, 0),
                ("Sat", "Saturation", 0, 100, 0),
                ("Lum", "Luminance", -100, 100, 0),
            ]:
                name = f"{prefix}{suffix}"
                slider = ParamSlider(name, label, mn, mx, default, 1, 0)
                slider.valueChanged.connect(self.paramChanged.emit)
                tab_layout.addWidget(slider)
                self.sliders[name] = slider

            tab_layout.addStretch()
            tabs.addTab(tab, region_label)

        # Blending + Balance
        blend = ParamSlider("ColorGradeBlending", "Blending", 0, 100, 50, 1, 0)
        blend.valueChanged.connect(self.paramChanged.emit)
        self.sliders["ColorGradeBlending"] = blend

        balance = ParamSlider("ColorGradeBalance", "Balance", -100, 100, 0, 1, 0)
        balance.valueChanged.connect(self.paramChanged.emit)
        self.sliders["ColorGradeBalance"] = balance

        layout.addWidget(tabs)
        layout.addWidget(blend)
        layout.addWidget(balance)

    def set_params(self, params: dict) -> None:
        for name, slider in self.sliders.items():
            if name in params:
                slider.set_value(params[name], emit=False)

    def get_params(self) -> dict:
        return {name: slider.value() for name, slider in self.sliders.items()}
