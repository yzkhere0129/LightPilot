"""Custom labeled slider with value display for parameter adjustment."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider
from PySide6.QtCore import Qt, Signal


class ParamSlider(QWidget):
    """A labeled slider: [Label] [====slider====] [value]

    Emits valueChanged(param_name, float_value) on change.
    Supports float ranges via internal integer scaling.
    """

    valueChanged = Signal(str, float)

    def __init__(
        self,
        param_name: str,
        label: str,
        min_val: float,
        max_val: float,
        default: float = 0.0,
        step: float = 1.0,
        decimals: int = 0,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.param_name = param_name
        self.min_val = min_val
        self.max_val = max_val
        self.default = default
        self.step = step
        self.decimals = decimals
        self._scale = int(1.0 / step) if step < 1 else 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        self.label = QLabel(label)
        self.label.setFixedWidth(130)
        self.label.setStyleSheet("color: #ccc; font-size: 12px;")

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(min_val * self._scale))
        self.slider.setMaximum(int(max_val * self._scale))
        self.slider.setValue(int(default * self._scale))
        self.slider.setFixedHeight(20)

        self.value_label = QLabel(self._format(default))
        self.value_label.setFixedWidth(50)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet("color: #fff; font-size: 12px;")

        layout.addWidget(self.label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)

        self.slider.valueChanged.connect(self._on_changed)

    def _format(self, val: float) -> str:
        if self.decimals == 0:
            return str(int(val))
        return f"{val:.{self.decimals}f}"

    def _on_changed(self, int_val: int) -> None:
        val = int_val / self._scale
        self.value_label.setText(self._format(val))
        self.valueChanged.emit(self.param_name, val)

    def value(self) -> float:
        return self.slider.value() / self._scale

    def set_value(self, val: float, emit: bool = True) -> None:
        if not emit:
            self.slider.blockSignals(True)
        self.slider.setValue(int(val * self._scale))
        self.value_label.setText(self._format(val))
        if not emit:
            self.slider.blockSignals(False)

    def reset(self) -> None:
        self.set_value(self.default)

    def mouseDoubleClickEvent(self, event):
        """Double-click to reset to default."""
        self.reset()
