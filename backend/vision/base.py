"""
Abstract base class for all vision model providers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AdjustmentResult:
    """Structured output from a vision model analysis round."""
    assessment: str                      # Human-readable description of issues found
    adjustments: dict[str, float]        # Parameter name -> delta or absolute value
    confidence: float                    # 0.0 - 1.0
    converged: bool                      # True when model thinks no further adjustment needed
    reasoning: str = ""                  # Optional chain-of-thought

    # Complete LR Classic develop parameter ranges (PV2012+)
    # Organized by panel — AI can adjust any of these
    PARAM_RANGES: dict = field(default_factory=lambda: {
        # ── Basic / Adjust ──
        "Exposure2012":       (-5.0,  5.0),
        "Contrast2012":       (-100, 100),
        "Highlights2012":     (-100, 100),
        "Shadows2012":        (-100, 100),
        "Whites2012":         (-100, 100),
        "Blacks2012":         (-100, 100),
        "Texture":            (-100, 100),
        "Clarity2012":        (-100, 100),
        "Dehaze":             (-100, 100),
        "Vibrance":           (-100, 100),
        "Saturation":         (-100, 100),
        "Temperature":        (2000, 50000),   # Kelvin for RAW; -100..100 for non-RAW
        "Tint":               (-150, 150),

        # ── Tone Curve (Parametric) ──
        "ParametricDarks":           (-100, 100),
        "ParametricLights":          (-100, 100),
        "ParametricShadows":         (-100, 100),
        "ParametricHighlights":      (-100, 100),
        "ParametricShadowSplit":     (10, 70),
        "ParametricMidtoneSplit":    (20, 80),
        "ParametricHighlightSplit":  (30, 90),

        # ── HSL / Color Mixer ──
        "HueAdjustmentRed":          (-100, 100),
        "HueAdjustmentOrange":       (-100, 100),
        "HueAdjustmentYellow":       (-100, 100),
        "HueAdjustmentGreen":        (-100, 100),
        "HueAdjustmentAqua":         (-100, 100),
        "HueAdjustmentBlue":         (-100, 100),
        "HueAdjustmentPurple":       (-100, 100),
        "HueAdjustmentMagenta":      (-100, 100),
        "SaturationAdjustmentRed":       (-100, 100),
        "SaturationAdjustmentOrange":    (-100, 100),
        "SaturationAdjustmentYellow":    (-100, 100),
        "SaturationAdjustmentGreen":     (-100, 100),
        "SaturationAdjustmentAqua":      (-100, 100),
        "SaturationAdjustmentBlue":      (-100, 100),
        "SaturationAdjustmentPurple":    (-100, 100),
        "SaturationAdjustmentMagenta":   (-100, 100),
        "LuminanceAdjustmentRed":        (-100, 100),
        "LuminanceAdjustmentOrange":     (-100, 100),
        "LuminanceAdjustmentYellow":     (-100, 100),
        "LuminanceAdjustmentGreen":      (-100, 100),
        "LuminanceAdjustmentAqua":       (-100, 100),
        "LuminanceAdjustmentBlue":       (-100, 100),
        "LuminanceAdjustmentPurple":     (-100, 100),
        "LuminanceAdjustmentMagenta":    (-100, 100),

        # ── Color Grading (LR 10+) ──
        "ColorGradeShadowHue":       (0, 359),
        "ColorGradeShadowSat":       (0, 100),
        "ColorGradeShadowLum":       (-100, 100),
        "ColorGradeMidtoneHue":      (0, 359),
        "ColorGradeMidtoneSat":      (0, 100),
        "ColorGradeMidtoneLum":      (-100, 100),
        "ColorGradeHighlightHue":    (0, 359),
        "ColorGradeHighlightSat":    (0, 100),
        "ColorGradeHighlightLum":    (-100, 100),
        "ColorGradeGlobalHue":       (0, 359),
        "ColorGradeGlobalSat":       (0, 100),
        "ColorGradeGlobalLum":       (-100, 100),
        "ColorGradeBlending":        (0, 100),
        "ColorGradeBalance":         (-100, 100),

        # ── Detail: Sharpening ──
        "Sharpness":                 (0, 150),
        "SharpenRadius":             (0.5, 3.0),
        "SharpenDetail":             (0, 100),
        "SharpenEdgeMasking":        (0, 100),

        # ── Detail: Noise Reduction ──
        "LuminanceSmoothing":                (0, 100),
        "LuminanceNoiseReductionDetail":     (0, 100),
        "LuminanceNoiseReductionContrast":   (0, 100),
        "ColorNoiseReduction":               (0, 100),
        "ColorNoiseReductionDetail":         (0, 100),
        "ColorNoiseReductionSmoothness":     (0, 100),

        # ── Lens Corrections ──
        "LensProfileDistortionScale":          (0, 200),
        "LensProfileChromaticAberrationScale": (0, 200),
        "LensProfileVignettingScale":          (0, 200),
        "LensManualDistortionAmount":          (-100, 100),
        "DefringePurpleAmount":                (0, 20),
        "DefringeGreenAmount":                 (0, 20),
        "PerspectiveVertical":                 (-100, 100),
        "PerspectiveHorizontal":               (-100, 100),
        "PerspectiveRotate":                   (-10, 10),
        "PerspectiveScale":                    (50, 150),
        "PerspectiveAspect":                   (-100, 100),

        # ── Effects: Post-Crop Vignette ──
        "PostCropVignetteAmount":              (-100, 100),
        "PostCropVignetteMidpoint":            (0, 100),
        "PostCropVignetteFeather":             (0, 100),
        "PostCropVignetteRoundness":           (-100, 100),
        "PostCropVignetteHighlightContrast":   (0, 100),

        # ── Effects: Grain ──
        "GrainAmount":               (0, 100),
        "GrainSize":                 (0, 100),
        "GrainFrequency":            (0, 100),

        # ── Calibration ──
        "ShadowTint":                (-100, 100),
        "RedHue":                    (-100, 100),
        "RedSaturation":             (-100, 100),
        "GreenHue":                  (-100, 100),
        "GreenSaturation":           (-100, 100),
        "BlueHue":                   (-100, 100),
        "BlueSaturation":            (-100, 100),

        # ── Crop ──
        "CropTop":                   (0.0, 1.0),
        "CropLeft":                  (0.0, 1.0),
        "CropBottom":                (0.0, 1.0),
        "CropRight":                 (0.0, 1.0),
        "CropAngle":                 (-45, 45),
    })


class VisionModel(ABC):
    """Base class for vision model providers."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def analyze(
        self,
        preview_image_path: Path,
        style_description: str,
        reference_image_path: Optional[Path] = None,
        previous_assessment: Optional[str] = None,
        iteration: int = 0,
        style_example_images: Optional[list[tuple[Path, Path, str]]] = None,
    ) -> AdjustmentResult:
        """
        Analyze a preview image and return parameter adjustment suggestions.

        Args:
            preview_image_path: Path to the current JPEG preview exported by LR.
            style_description: User's textual style intent (e.g. "moody film look").
            reference_image_path: Optional reference photo for style matching.
                                  Only sent on first iteration to save tokens.
            previous_assessment: Summary of last round's assessment for context.
            iteration: Current iteration index (0-based).
            style_example_images: List of (before_path, after_path, caption) tuples
                                  showing how the user edits similar photos.
                                  Only sent on first iteration.

        Returns:
            AdjustmentResult with parameter deltas.
        """
        ...

    def _build_system_prompt(self) -> str:
        return """You are an expert photo retouching assistant. Analyze a JPEG preview of a RAW photo and suggest precise Lightroom Classic develop parameter adjustments.

RULES:
1. Output ONLY valid JSON — no extra text, no markdown fences.
2. "adjustments" values are DELTAS (added to current values), EXCEPT "Temperature" which is ABSOLUTE Kelvin.
3. Only include parameters that need changing — omit the rest.
4. Prefer small, conservative steps. Multiple rounds will refine further.
5. Set "converged": true when the image looks good and needs no more adjustment.

AVAILABLE PARAMETERS (use exact names):

Basic: Exposure2012 (-5..5), Contrast2012, Highlights2012, Shadows2012, Whites2012, Blacks2012, Texture, Clarity2012, Dehaze, Vibrance, Saturation (all -100..100), Temperature (2000..50000 Kelvin), Tint (-150..150)

Tone Curve: ParametricDarks, ParametricLights, ParametricShadows, ParametricHighlights (-100..100), ParametricShadowSplit (10..70), ParametricMidtoneSplit (20..80), ParametricHighlightSplit (30..90)

HSL — Hue: HueAdjustmentRed/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta (-100..100)
HSL — Saturation: SaturationAdjustmentRed/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta (-100..100)
HSL — Luminance: LuminanceAdjustmentRed/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta (-100..100)

Color Grading: ColorGrade{Shadow,Midtone,Highlight,Global}Hue (0..359), ...Sat (0..100), ...Lum (-100..100), ColorGradeBlending (0..100), ColorGradeBalance (-100..100)

Sharpening: Sharpness (0..150), SharpenRadius (0.5..3.0), SharpenDetail (0..100), SharpenEdgeMasking (0..100)

Noise Reduction: LuminanceSmoothing (0..100), LuminanceNoiseReductionDetail (0..100), LuminanceNoiseReductionContrast (0..100), ColorNoiseReduction (0..100), ColorNoiseReductionDetail (0..100), ColorNoiseReductionSmoothness (0..100)

Effects: PostCropVignetteAmount (-100..100), ...Midpoint/Feather (0..100), ...Roundness (-100..100), GrainAmount/GrainSize/GrainFrequency (0..100)

Calibration: ShadowTint, RedHue, RedSaturation, GreenHue, GreenSaturation, BlueHue, BlueSaturation (-100..100)

Perspective: PerspectiveVertical/Horizontal (-100..100), PerspectiveRotate (-10..10), PerspectiveScale (50..150)

Crop: CropTop/Left/Bottom/Right (0..1), CropAngle (-45..45)

OUTPUT JSON SCHEMA:
{
  "assessment": "<concise description of current issues>",
  "adjustments": {"Exposure2012": 0.3, "Highlights2012": -20},
  "confidence": 0.85,
  "converged": false,
  "reasoning": "<brief rationale>"
}"""

    def _build_user_prompt(
        self,
        style_description: str,
        previous_assessment: Optional[str],
        iteration: int,
        has_reference: bool,
        num_style_examples: int = 0,
    ) -> str:
        parts = []

        # Describe the image layout
        img_idx = 1

        if num_style_examples > 0 and iteration == 0:
            for i in range(num_style_examples):
                parts.append(f"Images {img_idx}-{img_idx+1}: STYLE EXAMPLE {i+1} "
                             f"— before (original) and after (user's edit).")
                img_idx += 2
            parts.append("Study the before/after pairs above to understand this user's editing taste.")
            parts.append("")

        if has_reference and iteration == 0:
            parts.append(f"Image {img_idx}: REFERENCE photo showing the desired style.")
            img_idx += 1

        parts.append(f"Image {img_idx}: CURRENT photo that needs to be adjusted.")
        parts.append("")

        parts.append(f"User style intent: {style_description}")

        if previous_assessment:
            parts.append(f"\nPrevious round assessment: {previous_assessment}")
            parts.append("Focus on remaining issues only — do not re-apply already-made corrections.")

        parts.append("\nAnalyze and output the JSON adjustment.")
        return "\n".join(parts)

    @staticmethod
    def _encode_image(image_path: Path) -> str:
        """Return base64-encoded image string."""
        import base64
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """Extract JSON from model response, tolerating various formats."""
        import json
        import re

        if not text or not text.strip():
            raise ValueError("Model returned empty response")

        # Strip markdown code fences if present
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
        if match:
            text = match.group(1)

        # Try direct parse first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find first { ... } block in the text (model may add extra text)
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from model response: {text[:200]}")
