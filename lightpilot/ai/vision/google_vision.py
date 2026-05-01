"""Google Gemini vision provider."""
from pathlib import Path
from typing import Optional

from .base import VisionModel, AdjustmentResult


class GoogleVision(VisionModel):

    def __init__(self, config: dict):
        super().__init__(config)
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )

        genai.configure(api_key=config["api_key"])
        self._genai = genai
        self._model_name = config.get("model", "gemini-1.5-flash")

    def analyze(
        self,
        preview_image_path: Path,
        style_description: str,
        reference_image_path: Optional[Path] = None,
        previous_assessment: Optional[str] = None,
        iteration: int = 0,
        style_example_images: Optional[list[tuple[Path, Path, str]]] = None,
    ) -> AdjustmentResult:
        has_reference = reference_image_path is not None and iteration == 0
        examples = style_example_images or []
        num_examples = len(examples) if iteration == 0 else 0

        user_text = self._build_user_prompt(
            style_description, previous_assessment, iteration,
            has_reference, num_examples,
        )

        from PIL import Image as PILImage
        parts = []

        # Before/after style examples
        if num_examples > 0:
            for before_path, after_path, caption in examples:
                parts.append(PILImage.open(before_path))
                parts.append(PILImage.open(after_path))

        # Reference image
        if has_reference:
            parts.append(PILImage.open(reference_image_path))

        # Current preview
        parts.append(PILImage.open(preview_image_path))
        parts.append(user_text)

        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=self._build_system_prompt(),
        )

        response = model.generate_content(
            parts,
            generation_config={"temperature": 0.2, "max_output_tokens": 1024},
        )

        raw = response.text
        data = self._parse_json_response(raw)

        return AdjustmentResult(
            assessment=data.get("assessment", ""),
            adjustments=data.get("adjustments", {}),
            confidence=float(data.get("confidence", 0.7)),
            converged=bool(data.get("converged", False)),
            reasoning=data.get("reasoning", ""),
        )
