#!/usr/bin/env python3
"""
Offline integration test — verifies the full pipeline WITHOUT Lightroom.

Simulates the bridge file system, creates mock style history, and runs
the AI vision model against a real JPEG.

Usage:
  cd LightPilot
  pip install pyyaml openai   # (or anthropic / google-generativeai)

  # Edit config.yaml, fill in at least one API key

  # Test 1: Basic AI analysis (minimum viable test)
  python tests/test_offline.py test_basic photo.jpg

  # Test 2: AI analysis with style description
  python tests/test_offline.py test_style photo.jpg --style "warm film look"

  # Test 3: AI analysis with reference image
  python tests/test_offline.py test_reference photo.jpg --reference ref.jpg

  # Test 4: Style learner with mock catalog data
  python tests/test_offline.py test_learner photo.jpg

  # Test 5: Full pipeline simulation (mock bridge + AI + style learning)
  python tests/test_offline.py test_full photo.jpg

  # Run all tests
  python tests/test_offline.py all photo.jpg
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml


def load_config():
    for p in [Path("config.yaml"), Path(__file__).parent.parent / "config.yaml"]:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f)
    print("ERROR: config.yaml not found. Copy config.yaml and fill in an API key.")
    sys.exit(1)


def get_vision_model(config, provider=None):
    from backend.vision import create_vision_model
    return create_vision_model(config, provider)


# ─── Test 1: Basic AI analysis ──────────────────────────────

def test_basic(image_path: Path, config: dict, provider=None):
    """Send a single image to AI and check it returns valid JSON."""
    print("\n=== Test: Basic AI Analysis ===")
    print(f"Image: {image_path}")

    vision = get_vision_model(config, provider)
    result = vision.analyze(
        preview_image_path=image_path,
        style_description="Balanced exposure, natural colors",
        iteration=0,
    )

    print(f"  Assessment : {result.assessment}")
    print(f"  Adjustments: {json.dumps(result.adjustments, indent=4)}")
    print(f"  Confidence : {result.confidence:.2f}")
    print(f"  Converged  : {result.converged}")

    # Validate
    assert isinstance(result.assessment, str) and len(result.assessment) > 0, "Empty assessment"
    assert isinstance(result.adjustments, dict), "Adjustments not a dict"
    assert 0 <= result.confidence <= 1, f"Confidence out of range: {result.confidence}"
    assert isinstance(result.converged, bool), "Converged not bool"

    # Check parameter names are valid
    from backend.vision.base import AdjustmentResult
    dummy = AdjustmentResult(assessment="", adjustments={}, confidence=0, converged=False)
    valid_params = set(dummy.PARAM_RANGES.keys())
    for param in result.adjustments:
        if param not in valid_params:
            print(f"  WARNING: Unknown parameter '{param}' in adjustments")

    print("  PASSED")
    return result


# ─── Test 2: With style description ─────────────────────────

def test_style(image_path: Path, config: dict, style: str = "warm film look, lifted shadows, faded blacks", provider=None):
    """Verify AI adapts output to style description."""
    print(f"\n=== Test: Style-guided Analysis ===")
    print(f"Style: '{style}'")

    vision = get_vision_model(config, provider)
    result = vision.analyze(
        preview_image_path=image_path,
        style_description=style,
        iteration=0,
    )

    print(f"  Assessment : {result.assessment}")
    print(f"  Adjustments: {json.dumps(result.adjustments, indent=4)}")

    assert len(result.adjustments) > 0, "No adjustments suggested"
    print("  PASSED")
    return result


# ─── Test 3: With reference image ───────────────────────────

def test_reference(image_path: Path, config: dict, ref_path: Path = None, provider=None):
    """Verify AI accepts and uses a reference image."""
    if ref_path is None or not ref_path.exists():
        print("\n=== Test: Reference Image — SKIPPED (no --reference provided) ===")
        return None

    print(f"\n=== Test: Reference Image Analysis ===")
    print(f"Reference: {ref_path}")

    vision = get_vision_model(config, provider)
    result = vision.analyze(
        preview_image_path=image_path,
        style_description="Match the reference photo style",
        reference_image_path=ref_path,
        iteration=0,
    )

    print(f"  Assessment : {result.assessment}")
    print(f"  Adjustments: {json.dumps(result.adjustments, indent=4)}")

    assert len(result.adjustments) > 0, "No adjustments for reference matching"
    print("  PASSED")
    return result


# ─── Test 4: Style learner with mock data ────────────────────

def test_learner(image_path: Path, config: dict):
    """Create mock catalog history and test style matching."""
    print("\n=== Test: Style Learner (Mock Data) ===")

    from backend.style_learner import analyze_history, get_example_ids

    # Create mock history: 10 "golden hour portrait" edits + 5 "midday landscape" edits
    mock_history = []

    for i in range(10):
        mock_history.append({
            "id": str(100 + i),
            "develop": {
                "Exposure2012": 0.3 + (i * 0.05),
                "Highlights2012": -35 + (i * 2),
                "Shadows2012": 25 + (i * 3),
                "Temperature": 6200 + (i * 50),
                "Tint": -5,
                "Contrast2012": 15,
                "Clarity2012": -12,
                "Vibrance": 10,
                "SaturationAdjustmentOrange": -15,
                "ColorGradeShadowHue": 195,
                "ColorGradeShadowSat": 15,
                "GrainAmount": 20,
            },
            "exif": {
                "focalLength": 85,
                "aperture": 1.8,
                "isoSpeedRating": 200,
                "shutterSpeed": 0.005,
                "cameraModel": "Sony A7IV",
                "cameraMake": "Sony",
                "timeBucket": "golden_evening",
            },
        })

    for i in range(5):
        mock_history.append({
            "id": str(200 + i),
            "develop": {
                "Exposure2012": -0.3,
                "Highlights2012": -60,
                "Shadows2012": 40,
                "Temperature": 5200,
                "Contrast2012": 25,
                "Clarity2012": 20,
                "Vibrance": 15,
                "Dehaze": 15,
            },
            "exif": {
                "focalLength": 24,
                "aperture": 8.0,
                "isoSpeedRating": 100,
                "shutterSpeed": 0.01,
                "cameraModel": "Sony A7IV",
                "cameraMake": "Sony",
                "timeBucket": "midday",
            },
        })

    # Mock current photo: a golden hour portrait
    mock_current_exif = {
        "focalLength": 50,
        "aperture": 2.0,
        "isoSpeedRating": 320,
        "cameraModel": "Sony A7IV",
        "cameraMake": "Sony",
        "timeBucket": "golden_evening",
    }

    # Write mock files
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        history_path = tmpdir / "style_history.json"
        exif_path = tmpdir / "current_exif.json"

        with open(history_path, "w") as f:
            json.dump(mock_history, f)
        with open(exif_path, "w") as f:
            json.dump(mock_current_exif, f)

        # Test ID matching
        ids = get_example_ids(history_path, exif_path, top_n=3)
        print(f"  Top 3 similar IDs: {ids}")

        # Verify golden hour portraits ranked higher than midday landscapes
        assert all(int(id) < 200 for id in ids), (
            f"Expected golden hour photos (100-109), got {ids}"
        )

        # Test full analysis
        context = analyze_history(history_path, exif_path, top_n=3)
        print(f"  Total scanned: {context.total_scanned}")
        print(f"  Examples: {len(context.examples)}")

        for ex in context.examples:
            print(f"    ID {ex.photo_id}: similarity={ex.similarity:.2f}, "
                  f"has_images={ex.has_images}")

        text = context.to_prompt_text()
        print(f"\n  Prompt text preview (first 500 chars):")
        print(f"  {text[:500]}")

        assert context.total_scanned == 15
        assert len(context.examples) == 3
        assert all(ex.similarity > 0.5 for ex in context.examples)

    print("  PASSED")


# ─── Test 5: Full pipeline simulation ────────────────────────

def test_full(image_path: Path, config: dict, provider=None):
    """Simulate full pipeline: mock bridge → AI analysis → parameter output."""
    print("\n=== Test: Full Pipeline Simulation ===")

    vision = get_vision_model(config, provider)

    # Simulate iteration 0 with style context
    from backend.style_learner import StyleContext, StyleExample

    mock_examples = [
        StyleExample(
            photo_id="101",
            similarity=0.85,
            exif={"focalLength": 85, "aperture": 1.8, "timeBucket": "golden_evening",
                  "cameraModel": "Sony A7IV", "isoSpeedRating": 200},
            develop={"Exposure2012": 0.3, "Highlights2012": -35, "Shadows2012": 25,
                     "Temperature": 6200, "Contrast2012": 15, "Clarity2012": -12},
        )
    ]
    context = StyleContext(examples=mock_examples, total_scanned=50)

    style_text = context.to_prompt_text()
    full_style = style_text + "\n\nUser intent: match my usual golden hour portrait style"

    print("  Iteration 1 (with style context)...")
    r1 = vision.analyze(
        preview_image_path=image_path,
        style_description=full_style,
        iteration=0,
    )
    print(f"    Assessment: {r1.assessment}")
    print(f"    Adjustments: {r1.adjustments}")
    print(f"    Confidence: {r1.confidence:.2f}")

    # Simulate iteration 1 (follow-up, no images)
    print("  Iteration 2 (follow-up)...")
    r2 = vision.analyze(
        preview_image_path=image_path,
        style_description="match my usual golden hour portrait style",
        previous_assessment=r1.assessment,
        iteration=1,
    )
    print(f"    Assessment: {r2.assessment}")
    print(f"    Adjustments: {r2.adjustments}")
    print(f"    Confidence: {r2.confidence:.2f}")
    print(f"    Converged: {r2.converged}")

    assert isinstance(r1.adjustments, dict)
    assert isinstance(r2.adjustments, dict)
    print("  PASSED")


# ─── Test runner ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Offline tests for LightPilot")
    parser.add_argument("test", choices=["test_basic", "test_style", "test_reference",
                                          "test_learner", "test_full", "all"],
                        help="Which test to run")
    parser.add_argument("image", nargs="?", default=None, help="Path to test JPEG")
    parser.add_argument("--style", default="warm film look, lifted shadows")
    parser.add_argument("--reference", default=None)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config()

    image = Path(args.image) if args.image else None
    ref = Path(args.reference) if args.reference else None

    if args.test in ("test_learner",):
        # Learner test doesn't need an image for AI
        test_learner(image, config)
        return

    if not image or not image.exists():
        print(f"ERROR: image file required. Usage: python tests/test_offline.py {args.test} <photo.jpg>")
        sys.exit(1)

    tests = {
        "test_basic": lambda: test_basic(image, config, args.provider),
        "test_style": lambda: test_style(image, config, args.style, args.provider),
        "test_reference": lambda: test_reference(image, config, ref, args.provider),
        "test_learner": lambda: test_learner(image, config),
        "test_full": lambda: test_full(image, config, args.provider),
    }

    if args.test == "all":
        passed = 0
        failed = 0
        for name, fn in tests.items():
            try:
                fn()
                passed += 1
            except Exception as e:
                print(f"  FAILED: {e}")
                failed += 1
        print(f"\n=== Results: {passed} passed, {failed} failed ===")
    else:
        try:
            tests[args.test]()
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
