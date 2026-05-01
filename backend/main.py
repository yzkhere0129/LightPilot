"""
CLI entry point for LightPilot.

Usage:
  python -m backend.main [options]

Examples:
  # Start agent session (LR must be open with a photo selected)
  python -m backend.main --style "moody film look, low saturation"

  # With reference photo
  python -m backend.main --style "match this reference" --reference ./ref.jpg

  # Override model provider
  python -m backend.main --style "warm golden hour" --provider anthropic

  # Phase 0 standalone test (no LR needed)
  python -m backend.main --test ./preview.jpg --style "brighter, more contrast"
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .agent import AgentConfig, RetouchAgent, IterationRecord
from .lr_bridge import LRBridge
from .vision import create_vision_model

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_progress(record: IterationRecord) -> None:
    import json
    n = record.iteration + 1
    r = record.result
    bar = "#" * int(r.confidence * 20) + "-" * (20 - int(r.confidence * 20))
    print(f"\n  --- Iteration {n} ---")
    print(f"  Assessment : {r.assessment}")
    print(f"  Adjustments:")
    for k, v in r.adjustments.items():
        if isinstance(v, float):
            print(f"    {k:40s} {v:+.2f}")
        else:
            print(f"    {k:40s} {v:+d}" if isinstance(v, int) else f"    {k:40s} {v}")
    print(f"  Confidence : [{bar}] {r.confidence:.0%}")
    print(f"  Converged  : {'YES' if r.converged else 'no, continuing...'}")
    if r.reasoning:
        print(f"  Reasoning  : {r.reasoning}")


def run_phase0_test(args, config: dict) -> None:
    """
    Phase 0: standalone AI test without LR.
    Reads a JPEG, sends to AI, prints suggestions. No LR needed.
    """
    from .vision import create_vision_model

    preview = Path(args.test)
    if not preview.exists():
        print(f"Error: preview file not found: {preview}")
        sys.exit(1)

    provider = args.provider or None
    vision = create_vision_model(config, provider)
    ref = Path(args.reference) if args.reference else None

    print(f"[Phase 0 Test] Sending {preview.name} to AI...")
    result = vision.analyze(
        preview_image_path=preview,
        style_description=args.style,
        reference_image_path=ref,
        iteration=0,
    )

    print("\n=== AI Analysis Result ===")
    print(f"Assessment : {result.assessment}")
    print(f"Adjustments: {result.adjustments}")
    print(f"Confidence : {result.confidence:.2f}")
    print(f"Converged  : {result.converged}")
    if result.reasoning:
        print(f"Reasoning  : {result.reasoning}")


def run_learn_only(args, config: dict) -> None:
    """Scan LR catalog, compute and display context-aware style profile."""
    from .style_learner import analyze_history

    bridge_cfg = config.get("bridge", {})
    bridge = LRBridge(
        bridge_dir=bridge_cfg.get("directory", "~/.lightpilot"),
        poll_interval=bridge_cfg.get("poll_interval", 0.5),
        timeout=bridge_cfg.get("timeout", 30),
    )

    if not bridge.is_lr_running():
        print("Warning: LR plugin heartbeat not detected.")

    print("Requesting catalog scan from LR plugin...")
    bridge._write_status("scan_history")
    bridge._wait_for_status("scan_done")

    history_path = bridge.bridge_dir / "style_history.json"
    current_exif_path = bridge.bridge_dir / "current_exif.json"
    context = analyze_history(history_path, current_exif_path, top_n=5)

    print(f"\n=== Style Context ({context.total_scanned} photos, "
          f"{len(context.examples)} similar) ===\n")
    text = context.to_prompt_text()
    if text:
        print(text)
    else:
        print("No edited photos found in catalog.")


def run_agent_session(args, config: dict) -> None:
    """Full agent session connected to LR Classic via file bridge."""
    import sys
    # Ensure prints show immediately (not buffered)
    sys.stdout.reconfigure(line_buffering=True)

    provider = args.provider or None
    vision = create_vision_model(config, provider)

    bridge_cfg = config.get("bridge", {})
    bridge = LRBridge(
        bridge_dir=bridge_cfg.get("directory", "~/.lightpilot"),
        poll_interval=bridge_cfg.get("poll_interval", 0.5),
        timeout=bridge_cfg.get("timeout", 30),
    )

    print("=" * 60)
    print("  LightPilot - AI Photo Retouching Agent")
    print("=" * 60)
    print(f"  Provider : {provider or config['models']['default']}")
    print(f"  Style    : {args.style}")
    print(f"  Bridge   : {bridge.bridge_dir}")
    print()

    if not bridge.is_lr_running():
        print("  [!] LR plugin heartbeat NOT detected.")
        print("      Please make sure:")
        print("      1. Lightroom Classic is open")
        print("      2. A photo is selected in Develop module")
        print("      3. You clicked: File > Plug-in Extras > LightPilot - Start Session")
        print()

    agent_cfg_section = config.get("agent", {})
    style_learning_cfg = config.get("style_learning", {})

    agent_config = AgentConfig(
        max_iterations=agent_cfg_section.get("max_iterations", 5),
        convergence_threshold=agent_cfg_section.get("convergence_threshold", 0.1),
        style_description=args.style,
        reference_image_path=Path(args.reference) if args.reference else None,
        learn_from_catalog=not getattr(args, "no_learn", False) and style_learning_cfg.get("enabled", True),
        style_learning_config=style_learning_cfg,
    )

    agent = RetouchAgent(vision, bridge, agent_config)

    print(f"  Max iterations: {agent_config.max_iterations}")
    print(f"  Style learning: {'ON' if agent_config.learn_from_catalog else 'OFF'}")
    print()
    result = agent.run(progress_callback=print_progress)

    print(f"\n=== Session Complete ===")
    print(f"Converged      : {result.converged}")
    print(f"Iterations run : {result.iterations_run}")
    print(f"Message        : {result.message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LightPilot")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--style", required=True, help="Style description / intent")
    parser.add_argument("--reference", default=None, help="Path to reference JPEG for style matching")
    parser.add_argument("--provider", default=None,
                        help="Override model provider (openai/anthropic/google/ollama)")
    parser.add_argument("--test", default=None, metavar="JPEG",
                        help="Phase 0 standalone test: path to a JPEG, no LR needed")
    parser.add_argument("--no-learn", action="store_true",
                        help="Skip learning from LR catalog history")
    parser.add_argument("--learn-only", action="store_true",
                        help="Only scan catalog and print style profile, then exit")

    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    if args.learn_only:
        run_learn_only(args, config)
    elif args.test:
        run_phase0_test(args, config)
    else:
        run_agent_session(args, config)


if __name__ == "__main__":
    main()
