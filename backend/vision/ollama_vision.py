"""Ollama local vision model provider (LLaVA, moondream, etc.)."""
from pathlib import Path
from typing import Optional

from .base import VisionModel, AdjustmentResult


class OllamaVision(VisionModel):
    """Uses Ollama's OpenAI-compatible endpoint."""

    def __init__(self, config: dict):
        super().__init__(config)
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        base_url = config.get("base_url", "http://localhost:11434")
        self._client = OpenAI(
            base_url=f"{base_url.rstrip('/')}/v1",
            api_key="ollama",
        )
        self._model = config.get("model", "llava")

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

        content = []

        # Before/after style examples
        if num_examples > 0:
            for before_path, after_path, caption in examples:
                b_b64 = self._encode_image(before_path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b_b64}"},
                })
                a_b64 = self._encode_image(after_path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{a_b64}"},
                })

        if has_reference:
            ref_b64 = self._encode_image(reference_image_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"},
            })

        cur_b64 = self._encode_image(preview_image_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{cur_b64}"},
        })

        content.append({"type": "text", "text": user_text})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": content},
            ],
            max_tokens=1024,
            temperature=0.2,
        )

        raw = response.choices[0].message.content
        data = self._parse_json_response(raw)

        return AdjustmentResult(
            assessment=data.get("assessment", ""),
            adjustments=data.get("adjustments", {}),
            confidence=float(data.get("confidence", 0.7)),
            converged=bool(data.get("converged", False)),
            reasoning=data.get("reasoning", ""),
        )
