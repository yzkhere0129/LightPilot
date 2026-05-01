"""Effects panel: vignette and film grain."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Signal

from ...common.slider import ParamSlider


class EffectsPanel(QWidget):
    paramChanged = Signal(str, float)

    PARAMS = [
        ("PostCropVignetteAmount", "Vignette",    -100, 100, 0, 1, 0),
        ("GrainAmount",            "Grain Amount",  0,  100, 0, 1, 0),
        ("GrainSize",              "Grain Size",    0,  100, 25, 1, 0),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(1)

        header = QLabel("Effects")
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
        for name, slider in self.sliders.items():
            if name in params:
                slider.set_value(params[name], emit=False)

    def get_params(self) -> dict:
        return {name: slider.value() for name, slider in self.sliders.items()}
