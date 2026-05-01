"""Basic adjustment panel: exposure, contrast, highlights, shadows, whites, blacks, temperature, tint, vibrance, saturation."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

from ...common.slider import ParamSlider


class BasicPanel(QWidget):
    """Basic adjustments panel (matches LR Basic panel)."""

    paramChanged = Signal(str, float)

    PARAMS = [
        # (param_name, label, min, max, default, step, decimals)
        ("Temperature",    "Temperature",  2000, 50000, 6500, 100, 0),
        ("Tint",           "Tint",         -150, 150,   0,    1,   0),
        ("Exposure2012",   "Exposure",     -5.0, 5.0,   0.0,  0.05, 2),
        ("Contrast2012",   "Contrast",     -100, 100,   0,    1,   0),
        ("Highlights2012", "Highlights",   -100, 100,   0,    1,   0),
        ("Shadows2012",    "Shadows",      -100, 100,   0,    1,   0),
        ("Whites2012",     "Whites",       -100, 100,   0,    1,   0),
        ("Blacks2012",     "Blacks",       -100, 100,   0,    1,   0),
        ("Texture",        "Texture",      -100, 100,   0,    1,   0),
        ("Clarity2012",    "Clarity",      -100, 100,   0,    1,   0),
        ("Dehaze",         "Dehaze",       -100, 100,   0,    1,   0),
        ("Vibrance",       "Vibrance",     -100, 100,   0,    1,   0),
        ("Saturation",     "Saturation",   -100, 100,   0,    1,   0),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)

        header = QLabel("Basic")
        header.setStyleSheet("color: #fff; font-weight: bold; font-size: 13px; padding: 4px 0;")
        layout.addWidget(header)

        self.sliders: dict[str, ParamSlider] = {}
        for name, label, mn, mx, default, step, dec in self.PARAMS:
            slider = ParamSlider(name, label, mn, mx, default, step, dec)
            slider.valueChanged.connect(self.paramChanged.emit)
            layout.addWidget(slider)
            self.sliders[name] = slider

        layout.addStretch()

    def set_params(self, params: dict) -> None:
        """Set multiple slider values without emitting signals."""
        for name, slider in self.sliders.items():
            if name in params:
                slider.set_value(params[name], emit=False)

    def get_params(self) -> dict:
        """Get all current slider values."""
        return {name: slider.value() for name, slider in self.sliders.items()}

    def reset_all(self) -> None:
        for slider in self.sliders.values():
            slider.reset()
