#!/usr/bin/env python3
"""
Phase 0 standalone validation script.

Tests that the AI vision layer works correctly WITHOUT needing Lightroom.
Drop any JPEG into the script and verify the AI returns sensible parameter suggestions.

Usage:
  python phase0_test.py <image.jpg> [--style "your style"] [--provider openai]
  python phase0_test.py <image.jpg> --reference <ref.jpg> --style "match reference"
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def main():
    parser = argparse.ArgumentParser(description="Phase 0: Standalone AI vision test")
    parser.add_argument("image", help="Path to test JPEG")
    parser.add_argument("--style", default="Balanced exposure, neutral color, retain detail",
                        help="Style description to send to AI")
    parser.add_argument("--reference", default=None, help="Optional reference JPEG for style")
    parser.add_argument("--provider", default=None,
                        help="Provider override: openai / anthropic / google / ollama")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--iterations", type=int, default=1,
                        help="Number of analysis iterations to run (default: 1)")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        # Try relative to script location
        config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        print(f"Error: config.yaml not found at {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Import here so the script can be run from any working directory
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from backend.vision import create_vision_model

    provider = args.provider
    try:
        vision = create_vision_model(config, provider)
        print(f"Using provider: {provider or config['models']['default']}")
    except Exception as e:
        print(f"Failed to initialize model: {e}")
        sys.exit(1)

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Image not found: {image_path}")
        sys.exit(1)

    ref_path = Path(args.reference) if args.reference else None
    if ref_path and not ref_path.exists():
        print(f"Reference image not found: {ref_path}")
        sys.exit(1)

    print(f"Image    : {image_path}")
    print(f"Style    : {args.style}")
    if ref_path:
        print(f"Reference: {ref_path}")
    print(f"Iterations: {args.iterations}")
    print()

    previous_assessment = None
    for i in range(args.iterations):
        print(f"--- Iteration {i + 1} ---")
        result = vision.analyze(
            preview_image_path=image_path,
            style_description=args.style,
            reference_image_path=ref_path,
            previous_assessment=previous_assessment,
            iteration=i,
        )

        print(f"Assessment : {result.assessment}")
        print(f"Confidence : {result.confidence:.2f}")
        print(f"Converged  : {result.converged}")
        print(f"Adjustments:")
        print(json.dumps(result.adjustments, indent=4))
        if result.reasoning:
            print(f"Reasoning  : {result.reasoning}")
        print()

        if result.converged:
            print("Model reports converged, stopping.")
            break

        previous_assessment = result.assessment

    print("Phase 0 test complete.")


if __name__ == "__main__":
    main()
