"""Prompt builder — assembles structured, multi-layer prompts for the AI agent.

Architecture:
  Layer 1: SYSTEM — role definition + output format (static)
  Layer 2: ANALYSIS — structured photo analysis framework (static)
  Layer 3: RECIPE — matched style preset as a concrete starting point (dynamic)
  Layer 4: STRATEGY — iteration-specific instructions (dynamic per round)
  Layer 5: CONTEXT — current settings + previous feedback (dynamic per round)
"""

from __future__ import annotations

import json
from typing import Optional

from .styles import match_styles, blend_presets, STYLE_PRESETS

# ─────────────────────────────────────────────────────────────
# Layer 1: SYSTEM — Who you are, how to output
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a professional photo retouching expert. You analyze photographs and \
output precise editing parameters to achieve a specific visual style.

## OUTPUT FORMAT
Respond with ONLY a JSON object. No text before or after. No markdown fences.

```json
{
  "analysis": "<2-3 sentences: what you see in the photo and what needs to change>",
  "adjustments": {
    "Exposure2012": 0.4,
    "Shadows2012": 45,
    "Temperature": 6800
  },
  "confidence": 0.85,
  "converged": false,
  "reasoning": "<1-2 sentences: why these specific adjustments>"
}
```

## PARAMETER RULES
- All values are ABSOLUTE TARGETS (the desired final value, NOT a delta to add).
- Only include parameters you want to set. Omitted params keep their current value.
- Use 8-15 parameters per response for a cohesive style change.

## AVAILABLE PARAMETERS (exact names required)

**Exposure & Tone:**
Exposure2012 (-5.0 to 5.0), Contrast2012 (-100 to 100),
Highlights2012 (-100 to 100), Shadows2012 (-100 to 100),
Whites2012 (-100 to 100), Blacks2012 (-100 to 100)

**White Balance:**
Temperature (2000-50000 Kelvin), Tint (-150 to 150)

**Presence:**
Texture (-100 to 100), Clarity2012 (-100 to 100),
Dehaze (-100 to 100), Vibrance (-100 to 100), Saturation (-100 to 100)

**HSL (per channel — Red/Orange/Yellow/Green/Aqua/Blue/Purple/Magenta):**
HueAdjustment{Channel} (-100 to 100)
SaturationAdjustment{Channel} (-100 to 100)
LuminanceAdjustment{Channel} (-100 to 100)

**Color Grading:**
ColorGrade{Shadow,Midtone,Highlight}Hue (0-359)
ColorGrade{Shadow,Midtone,Highlight}Sat (0-100)

**Effects:**
PostCropVignetteAmount (-100 to 100), GrainAmount (0-100), GrainSize (0-100)

**Detail:**
Sharpness (0-150), LuminanceSmoothing (0-100)\
"""

# ─────────────────────────────────────────────────────────────
# Layer 2: ANALYSIS — How to think about the photo
# ─────────────────────────────────────────────────────────────

ANALYSIS_FRAMEWORK = """\
## ANALYSIS FRAMEWORK (follow this order)

1. **EXPOSURE** — Is the image too dark or too bright? Check highlights (blown?) and shadows (crushed?).
2. **COLOR TEMPERATURE** — Is it too warm (orange) or too cool (blue) for the target mood?
3. **TONAL CHARACTER** — Is contrast too harsh or too flat? Are blacks and whites clipping?
4. **COLOR PALETTE** — Which colors dominate? Which should be enhanced or muted for the style?
5. **STYLE GAP** — What is the biggest difference between the current look and the target style?\
"""

# ─────────────────────────────────────────────────────────────
# Layer 4: STRATEGY — What to focus on in each iteration
# ─────────────────────────────────────────────────────────────

ITERATION_STRATEGIES = {
    0: (
        "## ITERATION 1 — CORE TRANSFORMATION\n"
        "This is the first pass. Apply the fundamental style change:\n"
        "- Set exposure, contrast, highlights, shadows to establish the tonal foundation\n"
        "- Set white balance (Temperature) to establish the color mood\n"
        "- Set Vibrance/Saturation for overall color intensity\n"
        "- Apply color grading (shadow/highlight hue+saturation) for the signature look\n"
        "- Add effects (vignette, grain) if the style calls for them\n"
        "Make confident, visible changes. This is your main chance to define the style."
    ),
    1: (
        "## ITERATION 2 — COLOR REFINEMENT\n"
        "The basic style is set. Now refine the colors:\n"
        "- Fine-tune HSL channels — adjust individual color hue/saturation/luminance\n"
        "- Adjust color grading balance if shadows or highlights feel off\n"
        "- Tweak Temperature/Tint if the overall mood isn't quite right\n"
        "- Check if any color feels unnatural and correct it\n"
        "- You may also adjust exposure/contrast if the first pass was too aggressive or too subtle\n"
        "Make moderate adjustments. Build on what's working, fix what isn't."
    ),
    2: (
        "## ITERATION 3 — FINAL POLISH\n"
        "The style should be close. Make final micro-adjustments:\n"
        "- Fine-tune exposure and tone for perfect brightness\n"
        "- Check if any colors are distracting and mute them\n"
        "- Adjust detail (sharpness, noise reduction) if needed\n"
        "- Set converged=true if the image looks good — don't over-edit\n"
        "Less is more at this stage. Only change what truly needs changing."
    ),
}


def _get_iteration_strategy(iteration: int) -> str:
    if iteration in ITERATION_STRATEGIES:
        return ITERATION_STRATEGIES[iteration]
    return (
        f"## ITERATION {iteration + 1} — FINE-TUNING\n"
        "The style is established. Make only subtle refinements if needed.\n"
        "Set converged=true if the image matches the target style well."
    )


# ─────────────────────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────────────────────

class PromptBuilder:
    """Assembles multi-layer prompts for the AI vision model."""

    def build_system_prompt(self) -> str:
        """Static system prompt (Layer 1 + Layer 2)."""
        return f"{SYSTEM_PROMPT}\n\n{ANALYSIS_FRAMEWORK}"

    def build_user_prompt(
        self,
        style_description: str,
        iteration: int = 0,
        current_settings: dict | None = None,
        previous_analysis: str | None = None,
        has_reference: bool = False,
        num_style_examples: int = 0,
    ) -> str:
        """Dynamic user prompt (Layer 3 + Layer 4 + Layer 5)."""
        parts: list[str] = []

        # --- Image layout description ---
        img_idx = 1
        if num_style_examples > 0 and iteration == 0:
            for i in range(num_style_examples):
                parts.append(
                    f"Images {img_idx}-{img_idx+1}: STYLE EXAMPLE {i+1} "
                    f"— before (original) and after (user's edit)."
                )
                img_idx += 2
            parts.append("Study these before/after pairs to understand the user's taste.")
            parts.append("")

        if has_reference and iteration == 0:
            parts.append(f"Image {img_idx}: REFERENCE photo showing the desired style.")
            img_idx += 1

        parts.append(f"Image {img_idx}: The photo to edit.")
        parts.append("")

        # --- Layer 3: RECIPE from style presets ---
        parts.append(f'**Target style:** "{style_description}"')
        parts.append("")

        matched = match_styles(style_description)
        if matched:
            recipe = blend_presets(matched)
            style_names = " + ".join(
                f"{p['name_zh']} ({p['name_en']})" for p in matched
            )
            descriptions = " ".join(p["description"] for p in matched)
            avoids = " ".join(p.get("avoid", "") for p in matched)

            parts.append(f"**Matched styles:** {style_names}")
            parts.append(f"**Style character:** {descriptions}")
            parts.append("")
            parts.append("**Recommended recipe (adapt to this specific photo):**")
            parts.append("```")
            for k, v in sorted(recipe.items()):
                parts.append(f"  {k}: {v}")
            parts.append("```")
            parts.append(
                "Use this recipe as a STARTING POINT. Analyze the actual photo and "
                "adjust values up or down based on its specific exposure, lighting, "
                "and content. The recipe is a guide, not a rigid template."
            )
            if avoids:
                parts.append(f"\n**Avoid:** {avoids}")
            parts.append("")
        else:
            parts.append(
                "No preset matched. Interpret the style description freely "
                "and make a cohesive set of adjustments."
            )
            parts.append("")

        # --- Layer 4: STRATEGY ---
        parts.append(_get_iteration_strategy(iteration))
        parts.append("")

        # --- Layer 5: CONTEXT ---
        if current_settings and iteration > 0:
            parts.append("**Current settings (from previous iterations):**")
            parts.append("```")
            for k, v in sorted(current_settings.items()):
                if not k.startswith("_"):
                    parts.append(f"  {k}: {v}")
            parts.append("```")
            parts.append("")

        if previous_analysis and iteration > 0:
            parts.append(f"**Previous analysis:** {previous_analysis}")
            parts.append(
                "Review what was done. Refine values that need adjustment. "
                "Keep what's working well."
            )
            parts.append("")

        parts.append("Analyze the photo and output the JSON adjustment now.")
        return "\n".join(parts)
