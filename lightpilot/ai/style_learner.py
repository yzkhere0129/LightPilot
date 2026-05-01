"""
Style Learner — context-aware style learning from user's LR catalog.

Core idea: don't just read parameter numbers — show the AI actual before/after
images of how the user edits similar photos. The AI can SEE the aesthetic.

Flow:
  1. Lua plugin scans catalog (or user-selected photos) -> style_history.json
     Each entry: {id, develop: {...}, exif: {...}}
  2. Python matches current photo EXIF against history to find similar shots
  3. Python requests Lua to export before/after thumbnails of top N matches
  4. Python builds a prompt with: [before_img, after_img, settings] x N examples
  5. AI sees the user's taste directly from images, not just statistics
"""

import json
import logging
import math
import statistics
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

STYLE_PARAMS = [
    "Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012",
    "Whites2012", "Blacks2012", "Texture", "Clarity2012", "Dehaze",
    "Vibrance", "Saturation", "Temperature", "Tint",
    "ParametricDarks", "ParametricLights",
    "ParametricShadows", "ParametricHighlights",
    "HueAdjustmentRed", "HueAdjustmentOrange", "HueAdjustmentYellow",
    "HueAdjustmentGreen", "HueAdjustmentAqua", "HueAdjustmentBlue",
    "HueAdjustmentPurple", "HueAdjustmentMagenta",
    "SaturationAdjustmentRed", "SaturationAdjustmentOrange",
    "SaturationAdjustmentYellow", "SaturationAdjustmentGreen",
    "SaturationAdjustmentAqua", "SaturationAdjustmentBlue",
    "SaturationAdjustmentPurple", "SaturationAdjustmentMagenta",
    "LuminanceAdjustmentRed", "LuminanceAdjustmentOrange",
    "LuminanceAdjustmentYellow", "LuminanceAdjustmentGreen",
    "LuminanceAdjustmentAqua", "LuminanceAdjustmentBlue",
    "LuminanceAdjustmentPurple", "LuminanceAdjustmentMagenta",
    "ColorGradeShadowHue", "ColorGradeShadowSat",
    "ColorGradeMidtoneHue", "ColorGradeMidtoneSat",
    "ColorGradeHighlightHue", "ColorGradeHighlightSat",
    "ColorGradeGlobalHue", "ColorGradeGlobalSat",
    "ColorGradeBlending", "ColorGradeBalance",
    "PostCropVignetteAmount", "GrainAmount", "GrainSize",
    "ShadowTint", "RedHue", "RedSaturation",
    "GreenHue", "GreenSaturation", "BlueHue", "BlueSaturation",
    "Sharpness", "LuminanceSmoothing", "ColorNoiseReduction",
]


# ──────────────────────────────────────────────────────────────
# EXIF similarity scoring
# ──────────────────────────────────────────────────────────────

def _similarity_score(current_exif: dict, history_exif: dict) -> float:
    score = 0.0
    weights_total = 0.0

    # Time of day (weight 3)
    w = 3.0
    weights_total += w
    cb = current_exif.get("timeBucket", "")
    hb = history_exif.get("timeBucket", "")
    if cb and hb:
        if cb == hb:
            score += w
        elif {cb, hb} <= {"golden_morning", "golden_evening"}:
            score += w * 0.7
        else:
            score += w * 0.1

    # ISO (weight 2)
    w = 2.0
    weights_total += w
    ci = current_exif.get("isoSpeedRating")
    hi = history_exif.get("isoSpeedRating")
    if ci and hi and ci > 0 and hi > 0:
        lr = abs(math.log2(ci) - math.log2(hi))
        score += w * max(0, 1 - lr / 4)
    else:
        score += w * 0.3

    # Focal length (weight 2)
    w = 2.0
    weights_total += w
    cf = current_exif.get("focalLength")
    hf = history_exif.get("focalLength")
    if cf and hf and cf > 0 and hf > 0:
        lr = abs(math.log2(cf) - math.log2(hf))
        score += w * max(0, 1 - lr / 3)
    else:
        score += w * 0.3

    # Camera model (weight 2)
    w = 2.0
    weights_total += w
    cc = current_exif.get("cameraModel", "")
    hc = history_exif.get("cameraModel", "")
    if cc and hc:
        if cc == hc:
            score += w
        elif current_exif.get("cameraMake", "") == history_exif.get("cameraMake", ""):
            score += w * 0.5
        else:
            score += w * 0.1
    else:
        score += w * 0.3

    # Aperture (weight 1)
    w = 1.0
    weights_total += w
    ca = current_exif.get("aperture")
    ha = history_exif.get("aperture")
    if ca and ha and ca > 0 and ha > 0:
        score += w * max(0, 1 - abs(ca - ha) / 8)
    else:
        score += w * 0.3

    return score / weights_total if weights_total > 0 else 0.0


def _find_similar_photos(
    current_exif: dict, history: list[dict], top_n: int = 5
) -> list[tuple[float, dict]]:
    scored = []
    for entry in history:
        s = _similarity_score(current_exif, entry.get("exif", {}))
        scored.append((s, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_n]


# ──────────────────────────────────────────────────────────────
# Format helpers
# ──────────────────────────────────────────────────────────────

def _format_develop_nondefault(develop: dict) -> dict:
    result = {}
    for param in STYLE_PARAMS:
        val = develop.get(param)
        if val is None:
            continue
        if param == "Temperature":
            result[param] = round(val)
        elif param == "Sharpness" and abs(val - 40) <= 3:
            continue
        elif param == "ColorNoiseReduction" and abs(val - 25) <= 3:
            continue
        elif abs(val) > 1:
            result[param] = round(val, 1) if isinstance(val, float) else val
    return result


def _describe_exif(exif: dict) -> str:
    parts = []
    if exif.get("focalLength"):
        parts.append("{}mm".format(int(exif["focalLength"])))
    if exif.get("aperture"):
        parts.append("f/{:.1f}".format(exif["aperture"]))
    if exif.get("shutterSpeed"):
        ss = exif["shutterSpeed"]
        parts.append("1/{:.0f}s".format(1 / ss) if ss < 1 else "{:.1f}s".format(ss))
    if exif.get("isoSpeedRating"):
        parts.append("ISO {}".format(int(exif["isoSpeedRating"])))
    if exif.get("timeBucket"):
        parts.append(exif["timeBucket"].replace("_", " "))
    if exif.get("cameraModel"):
        parts.append(exif["cameraModel"])
    return " | ".join(parts) if parts else "unknown"


def _settings_to_compact_str(settings: dict) -> str:
    parts = []
    for k, v in sorted(settings.items()):
        if isinstance(v, float):
            parts.append("{}={:+.1f}".format(k, v))
        elif isinstance(v, int) and k != "Temperature":
            parts.append("{}={:+d}".format(k, v))
        else:
            parts.append("{}={}".format(k, v))
    return ", ".join(parts)


# ──────────────────────────────────────────────────────────────
# StyleContext — holds matched examples + their image paths
# ──────────────────────────────────────────────────────────────

class StyleExample:
    """One before/after example from the user's catalog."""

    def __init__(
        self,
        photo_id: str,
        similarity: float,
        exif: dict,
        develop: dict,
        before_thumb: Optional[Path] = None,
        after_thumb: Optional[Path] = None,
    ):
        self.photo_id = photo_id
        self.similarity = similarity
        self.exif = exif
        self.develop = develop  # non-default develop settings
        self.before_thumb = before_thumb
        self.after_thumb = after_thumb

    @property
    def has_images(self) -> bool:
        return (self.before_thumb is not None and self.before_thumb.exists() and
                self.after_thumb is not None and self.after_thumb.exists())


class StyleContext:
    """Holds style examples with optional before/after images."""

    def __init__(self, examples: list[StyleExample], total_scanned: int):
        self.examples = examples
        self.total_scanned = total_scanned

    @property
    def has_visual_examples(self) -> bool:
        return any(ex.has_images for ex in self.examples)

    def to_prompt_text(self) -> str:
        """Text portion of style context (always included in prompt)."""
        if not self.examples:
            return ""

        lines = [
            "USER EDITING STYLE (from {} most similar photos in their catalog of {}):".format(
                len(self.examples), self.total_scanned),
            ""
        ]

        for i, ex in enumerate(self.examples, 1):
            filtered = _format_develop_nondefault(ex.develop)
            if not filtered:
                continue

            has_img = " [before/after images attached]" if ex.has_images else ""
            lines.append("  Example {} (similarity: {:.0%}, {}):{}".format(
                i, ex.similarity, _describe_exif(ex.exif), has_img))
            lines.append("    Settings: " + _settings_to_compact_str(filtered))
            lines.append("")

        lines.append("IMPORTANT: The examples show this user's actual editing taste on similar photos.")
        if self.has_visual_examples:
            lines.append("Look at the before/after image pairs to understand the visual transformation,")
            lines.append("not just the parameter numbers. Replicate the same aesthetic feel.")
        lines.append("Adapt to the current image while maintaining the user's style.")
        return "\n".join(lines)

    def get_image_pairs(self) -> list[tuple[Path, Path, str]]:
        """Return (before_path, after_path, caption) for examples that have images."""
        pairs = []
        for i, ex in enumerate(self.examples, 1):
            if ex.has_images:
                caption = "Example {} ({})".format(i, _describe_exif(ex.exif))
                pairs.append((ex.before_thumb, ex.after_thumb, caption))
        return pairs


# ──────────────────────────────────────────────────────────────
# Main API
# ──────────────────────────────────────────────────────────────

def analyze_history(
    history_path: Path,
    current_exif_path: Optional[Path] = None,
    thumbs_dir: Optional[Path] = None,
    top_n: int = 5,
) -> StyleContext:
    """
    Analyze style history and return a StyleContext with matched examples.

    Args:
        history_path: style_history.json [{id, develop, exif}, ...]
        current_exif_path: current_exif.json for similarity matching
        thumbs_dir: directory containing {id}_before.jpg / {id}_after.jpg
        top_n: number of examples to return
    """
    if not history_path.exists():
        log.warning("Style history not found: %s", history_path)
        return StyleContext([], 0)

    with open(history_path, encoding="utf-8") as f:
        history = json.load(f)

    if not history:
        return StyleContext([], 0)

    n = len(history)
    log.info("Loaded %d edited photos from catalog", n)

    # Load current EXIF
    current_exif = {}
    if current_exif_path and current_exif_path.exists():
        with open(current_exif_path, encoding="utf-8") as f:
            current_exif = json.load(f)
        log.info("Current photo: %s", _describe_exif(current_exif))

    # Find similar
    if current_exif:
        matches = _find_similar_photos(current_exif, history, top_n)
    else:
        matches = [(0.5, e) for e in history[:top_n]]

    # Build StyleExamples
    examples = []
    for score, entry in matches:
        photo_id = str(entry.get("id", ""))
        before_thumb = None
        after_thumb = None
        if thumbs_dir and photo_id:
            bp = thumbs_dir / "{}_before.jpg".format(photo_id)
            ap = thumbs_dir / "{}_after.jpg".format(photo_id)
            if bp.exists() and ap.exists():
                before_thumb = bp
                after_thumb = ap

        examples.append(StyleExample(
            photo_id=photo_id,
            similarity=score,
            exif=entry.get("exif", {}),
            develop=entry.get("develop", {}),
            before_thumb=before_thumb,
            after_thumb=after_thumb,
        ))

    return StyleContext(examples, n)


def get_example_ids(
    history_path: Path,
    current_exif_path: Optional[Path] = None,
    top_n: int = 5,
) -> list[str]:
    """
    Quick pass: just return the photo IDs of the top N similar photos.
    Used by the agent to request thumbnail exports from Lua before full analysis.
    """
    if not history_path.exists():
        return []

    with open(history_path, encoding="utf-8") as f:
        history = json.load(f)
    if not history:
        return []

    current_exif = {}
    if current_exif_path and current_exif_path.exists():
        with open(current_exif_path, encoding="utf-8") as f:
            current_exif = json.load(f)

    if current_exif:
        matches = _find_similar_photos(current_exif, history, top_n)
    else:
        matches = [(0.5, e) for e in history[:top_n]]

    return [str(entry.get("id", "")) for _, entry in matches if entry.get("id")]
