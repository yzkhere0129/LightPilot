"""AI Retouching Agent — core iteration loop (standalone version).

Orchestrates:
  1. PipelineBridge: render preview, apply parameter updates
  2. VisionModel: analyze preview, produce AdjustmentResult
  3. Convergence detection: stop when model says converged or max iterations reached
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from .pipeline_bridge import PipelineBridge
from .vision import VisionModel, AdjustmentResult

log = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    max_iterations: int = 5
    convergence_threshold: float = 0.1   # min confidence improvement to keep going
    style_description: str = ""
    reference_image_path: Optional[Path] = None
    learn_from_catalog: bool = False      # disabled by default (no LR catalog)
    style_learning_config: Optional[dict] = None


@dataclass
class IterationRecord:
    iteration: int
    settings_before: dict
    result: AdjustmentResult
    settings_after: dict


@dataclass
class SessionResult:
    converged: bool
    iterations_run: int
    history: list[IterationRecord] = field(default_factory=list)
    final_settings: dict = field(default_factory=dict)
    message: str = ""


ProgressCallback = Callable[[IterationRecord], None]


class RetouchAgent:

    def __init__(
        self,
        vision_model: VisionModel,
        bridge: PipelineBridge,
        agent_config: AgentConfig,
    ):
        self.vision = vision_model
        self.bridge = bridge
        self.config = agent_config

    def run(self, progress_callback: Optional[ProgressCallback] = None) -> SessionResult:
        """Execute the full iterative retouching session.

        Returns SessionResult with history and final settings.
        """
        self.bridge.reset()

        history: list[IterationRecord] = []
        previous_assessment: Optional[str] = None
        prev_confidence: float = 0.0

        for i in range(self.config.max_iterations):
            log.info("--- Iteration %d/%d ---", i + 1, self.config.max_iterations)

            # 1. Render current preview
            settings_before, preview_path = self.bridge.request_export()
            log.info("Preview: %s", preview_path)

            # 2. Ask vision model to analyze
            result = self.vision.analyze(
                preview_image_path=preview_path,
                style_description=self.config.style_description,
                reference_image_path=self.config.reference_image_path,
                previous_assessment=previous_assessment,
                iteration=i,
                current_settings=settings_before if i > 0 else None,
            )

            log.info(
                "Assessment: %s | confidence=%.2f | converged=%s",
                result.assessment, result.confidence, result.converged,
            )

            # 3. Apply adjustments
            if result.adjustments:
                self.bridge.send_adjustments(result.adjustments)
                log.info("Applied: %s", result.adjustments)
            else:
                log.info("No adjustments suggested.")

            # 4. Record
            settings_after = self.bridge.get_current_settings() or settings_before
            record = IterationRecord(
                iteration=i,
                settings_before=settings_before,
                result=result,
                settings_after=settings_after,
            )
            history.append(record)

            if progress_callback:
                progress_callback(record)

            # 5. Convergence checks
            if result.converged:
                log.info("Model reports converged.")
                return SessionResult(
                    converged=True,
                    iterations_run=i + 1,
                    history=history,
                    final_settings=settings_after,
                    message=f"Converged after {i + 1} iterations.",
                )

            confidence_gain = result.confidence - prev_confidence
            if i > 0 and confidence_gain < self.config.convergence_threshold:
                log.info(
                    "Confidence gain %.3f < threshold %.3f; stopping early.",
                    confidence_gain, self.config.convergence_threshold,
                )
                return SessionResult(
                    converged=True,
                    iterations_run=i + 1,
                    history=history,
                    final_settings=settings_after,
                    message=f"Early stop: confidence plateau after {i + 1} iterations.",
                )

            previous_assessment = result.assessment
            prev_confidence = result.confidence

        log.info("Reached max iterations (%d).", self.config.max_iterations)
        final_settings = history[-1].settings_after if history else {}
        return SessionResult(
            converged=False,
            iterations_run=self.config.max_iterations,
            history=history,
            final_settings=final_settings,
            message=f"Stopped at max {self.config.max_iterations} iterations.",
        )
