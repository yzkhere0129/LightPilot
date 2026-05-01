"""AI auto-retouching panel.

Allows the user to type a style description and click 'Auto Retouch'
to trigger the AI agent, watching each iteration in real-time.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QProgressBar, QComboBox,
)
from PySide6.QtCore import Signal, QThread, QObject


class AiWorker(QObject):
    """Runs the AI agent in a background thread."""
    iterationDone = Signal(int, str, dict)  # iteration, assessment, adjustments
    finished = Signal(str, dict)            # message, final_settings
    error = Signal(str)

    def __init__(self, source_path: str, style: str, provider: str | None, config: dict):
        super().__init__()
        self.source_path = source_path
        self.style = style
        self.provider = provider
        self.config = config

    def run(self):
        try:
            from ...ai.vision import create_vision_model
            from ...ai.pipeline_bridge import PipelineBridge
            from ...ai.agent import RetouchAgent, AgentConfig

            vision = create_vision_model(self.config, provider=self.provider)
            bridge = PipelineBridge(self.source_path)
            agent_config = AgentConfig(
                max_iterations=self.config.get("agent", {}).get("max_iterations", 5),
                convergence_threshold=self.config.get("agent", {}).get("convergence_threshold", 0.1),
                style_description=self.style,
            )
            agent = RetouchAgent(vision, bridge, agent_config)

            def on_progress(record):
                self.iterationDone.emit(
                    record.iteration + 1,
                    record.result.assessment,
                    record.result.adjustments,
                )

            result = agent.run(progress_callback=on_progress)
            self.finished.emit(result.message, result.final_settings)
        except Exception as e:
            self.error.emit(str(e))


class AiPanel(QWidget):
    """AI auto-retouching panel."""

    applySettings = Signal(dict)  # emitted with final AI settings

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: QThread | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("AI Retouch")
        header.setStyleSheet("color: #fff; font-weight: bold; font-size: 13px; padding: 4px 0;")
        layout.addWidget(header)

        # Style input
        self.style_input = QLineEdit()
        self.style_input.setPlaceholderText("Describe the style (e.g. 'warm film look')...")
        self.style_input.setStyleSheet(
            "background: #333; color: #fff; border: 1px solid #555; "
            "border-radius: 3px; padding: 6px;"
        )
        layout.addWidget(self.style_input)

        # Provider selector
        row = QHBoxLayout()
        row.addWidget(QLabel("Provider:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["(default)", "mimo", "openai", "anthropic", "google", "ollama"])
        self.provider_combo.setStyleSheet("background: #333; color: #fff;")
        row.addWidget(self.provider_combo, 1)
        layout.addLayout(row)

        # Buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Auto Retouch")
        self.start_btn.setStyleSheet(
            "background: #2563eb; color: #fff; font-weight: bold; "
            "padding: 8px 16px; border-radius: 4px;"
        )
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(
            "background: #444; color: #999; padding: 8px 12px; border-radius: 4px;"
        )
        btn_row.addWidget(self.stop_btn)
        layout.addLayout(btn_row)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 5)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Idle")
        self.progress.setStyleSheet(
            "QProgressBar { background: #333; border: none; height: 16px; }"
            "QProgressBar::chunk { background: #2563eb; }"
        )
        layout.addWidget(self.progress)

        # Log output
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        self.log.setStyleSheet(
            "background: #1a1a1a; color: #aaa; font-family: monospace; "
            "font-size: 11px; border: 1px solid #333;"
        )
        layout.addWidget(self.log)

        # State
        self._source_path: str | None = None
        self._config: dict = {}

    def set_source(self, path: str):
        self._source_path = path

    def set_config(self, config: dict):
        self._config = config

    def _on_start(self):
        if not self._source_path:
            self.log.append("No image loaded.")
            return

        style = self.style_input.text().strip()
        if not style:
            self.log.append("Please enter a style description.")
            return

        provider_text = self.provider_combo.currentText()
        provider = None if provider_text == "(default)" else provider_text

        self.log.clear()
        self.log.append(f"Starting AI retouch: '{style}'")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setValue(0)
        self.progress.setFormat("Starting...")

        # Run in background thread
        self._thread = QThread()
        self._worker = AiWorker(self._source_path, style, provider, self._config)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.iterationDone.connect(self._on_iteration)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _on_iteration(self, iteration: int, assessment: str, adjustments: dict):
        self.progress.setValue(iteration)
        self.progress.setFormat(f"Iteration {iteration}")
        adj_str = ", ".join(f"{k}: {v:+.1f}" if isinstance(v, float) else f"{k}: {v:+d}"
                           for k, v in list(adjustments.items())[:5])
        if len(adjustments) > 5:
            adj_str += f" (+{len(adjustments)-5} more)"
        self.log.append(f"\n[Iter {iteration}] {assessment}")
        self.log.append(f"  {adj_str}")

    def _on_finished(self, message: str, settings: dict):
        self.log.append(f"\n{message}")
        self.progress.setFormat("Done")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None

        if settings:
            self.applySettings.emit(settings)

    def _on_error(self, err: str):
        self.log.append(f"\nError: {err}")
        self.progress.setFormat("Error")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
            self._thread = None
