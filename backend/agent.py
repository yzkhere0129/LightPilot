"""
AI Retouching Agent — core iteration loop.

Orchestrates:
  1. LRBridge: request preview from LR, send parameter updates back
  2. VisionModel: analyze preview, produce AdjustmentResult
  3. Convergence detection: stop when model says converged or max iterations reached
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from .lr_bridge import LRBridge
from .vision import VisionModel, AdjustmentResult

log = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    max_iterations: int = 5
    convergence_threshold: float = 0.1   # min confidence improvement to keep going
    style_description: str = ""
    reference_image_path: Optional[Path] = None
    learn_from_catalog: bool = True       # scan LR catalog for user style
    style_learning_config: Optional[dict] = None  # from config.yaml style_learning section


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


# Callback type: called after each iteration with the current record
ProgressCallback = Callable[[IterationRecord], None]


class RetouchAgent:

    def __init__(
        self,
        vision_model: VisionModel,
        bridge: LRBridge,
        agent_config: AgentConfig,
    ):
        self.vision = vision_model
        self.bridge = bridge
        self.config = agent_config

    def _learn_user_style(self) -> Optional['StyleContext']:
        """
        Full style learning pipeline:
          1. Request LR to scan catalog (or selected photos)
          2. Find similar photos by EXIF matching
          3. Request LR to export before/after thumbnails
          4. Return StyleContext with images + text
        """
        if not self.config.learn_from_catalog:
            return None

        from .style_learner import analyze_history, get_example_ids
        import json

        bridge_dir = self.bridge.bridge_dir
        history_path = bridge_dir / "style_history.json"
        current_exif_path = bridge_dir / "current_exif.json"
        thumbs_dir = bridge_dir / "thumbs"

        style_cfg = self.config.style_learning_config or {}
        source = style_cfg.get("source", "auto")
        top_n = style_cfg.get("top_n_examples", 5)
        include_images = style_cfg.get("include_before_after", True)

        # Step 1: Scan catalog
        scan_cmd = "scan_selected" if source == "selected" else "scan_history"
        try:
            self.bridge._write_status(scan_cmd)
            self.bridge._wait_for_status("scan_done")
            log.info("Catalog scan complete (source=%s)", source)
        except Exception as e:
            log.warning("Catalog scan failed: %s", e)
            return None

        # Step 2: Find similar photo IDs
        ids = get_example_ids(history_path, current_exif_path, top_n)
        if not ids:
            log.info("No similar photos found in history")
            return None
        log.info("Found %d similar photos: %s", len(ids), ids)

        # Step 3: Request before/after thumbnails
        if include_images and ids:
            try:
                req_path = bridge_dir / "export_thumbs_request.json"
                req_path.write_text(json.dumps({"ids": ids}), encoding="utf-8")
                self.bridge._write_status("export_thumbs")
                self.bridge._wait_for_status("thumbs_done")
                log.info("Thumbnail export complete")
            except Exception as e:
                log.warning("Thumbnail export failed: %s — continuing with text only", e)

        # Step 4: Build full context
        context = analyze_history(
            history_path, current_exif_path,
            thumbs_dir=thumbs_dir if include_images else None,
            top_n=top_n,
        )
        log.info("Style context: %d examples, %d with images, %d total scanned",
                 len(context.examples),
                 sum(1 for ex in context.examples if ex.has_images),
                 context.total_scanned)
        return context

    def run(self, progress_callback: Optional[ProgressCallback] = None) -> SessionResult:
        """
        Execute the full iterative retouching session.

        Returns SessionResult with history and final settings.
        """
        self.bridge.reset()

        # Learn user style from catalog before starting iterations
        style_context = self._learn_user_style()
        if style_context:
            log.info("Injecting user style profile into prompts")

        history: list[IterationRecord] = []
        previous_assessment: Optional[str] = None
        prev_confidence: float = 0.0

        for i in range(self.config.max_iterations):
            log.info(f"--- Iteration {i + 1}/{self.config.max_iterations} ---")

            # 1. Export current preview from LR
            settings_before, preview_path = self.bridge.request_export()
            log.info(f"Got preview: {preview_path}")

            # 2. Ask vision model to analyze
            # First iteration: inject style context (text + images)
            full_style = self.config.style_description
            style_images = []

            if style_context and i == 0:
                full_style = style_context.to_prompt_text() + "\n\n" + full_style
                # Collect before/after image pairs
                style_images = style_context.get_image_pairs()
                if style_images:
                    log.info("Sending %d before/after image pairs to AI", len(style_images))

            result = self.vision.analyze(
                preview_image_path=preview_path,
                style_description=full_style,
                reference_image_path=self.config.reference_image_path,
                previous_assessment=previous_assessment,
                iteration=i,
                style_example_images=style_images,
            )

            log.info(
                f"Assessment: {result.assessment} | "
                f"confidence={result.confidence:.2f} | converged={result.converged}"
            )

            # 3. Apply adjustments to LR
            if result.adjustments:
                self.bridge.send_adjustments(result.adjustments)
                log.info(f"Applied: {result.adjustments}")
            else:
                log.info("No adjustments suggested.")

            # 4. Fetch updated settings
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
                    f"Confidence gain {confidence_gain:.3f} < threshold "
                    f"{self.config.convergence_threshold:.3f}; stopping early."
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

        log.info(f"Reached max iterations ({self.config.max_iterations}).")
        final_settings = history[-1].settings_after if history else {}
        return SessionResult(
            converged=False,
            iterations_run=self.config.max_iterations,
            history=history,
            final_settings=final_settings,
            message=f"Stopped at max {self.config.max_iterations} iterations.",
        )
