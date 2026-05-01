"""AI CLI entry point: python -m lightpilot.ai photo.ARW --style "warm film" --output result.jpg

Runs the AI retouching agent on a photo without any manual intervention.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lightpilot.ai",
        description="LightPilot AI Agent — automated photo retouching",
    )
    parser.add_argument("input", help="Input image file (RAW or standard)")
    parser.add_argument(
        "--style", "-s", required=True,
        help='Style description (e.g. "moody film", "bright and airy")',
    )
    parser.add_argument("--output", "-o", required=True, help="Output file path")
    parser.add_argument("--reference", "-r", default=None, help="Reference image for style matching")
    parser.add_argument("--provider", "-p", default=None, help="Vision model provider override")
    parser.add_argument("--iterations", "-n", type=int, default=5, help="Max iterations (default 5)")
    parser.add_argument("--proxy", type=int, default=2_000_000, help="Proxy pixels (default 2M)")
    parser.add_argument("--quality", "-q", type=int, default=95, help="Output JPEG quality")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--full-res", action="store_true",
        help="Export at full resolution (default: proxy resolution)",
    )
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    # Load config
    import yaml
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    if not config_path.exists():
        print(f"Error: config.yaml not found at {config_path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Create vision model
    from .vision import create_vision_model
    vision = create_vision_model(config, provider=args.provider)
    print(f"Vision model: {args.provider or config['models']['default']}")

    # Create pipeline bridge
    from .pipeline_bridge import PipelineBridge
    bridge = PipelineBridge(
        source_path=input_path,
        proxy_pixels=args.proxy,
    )

    # Create agent
    from .agent import RetouchAgent, AgentConfig
    agent_config = AgentConfig(
        max_iterations=args.iterations,
        convergence_threshold=config.get("agent", {}).get("convergence_threshold", 0.1),
        style_description=args.style,
        reference_image_path=Path(args.reference) if args.reference else None,
    )

    agent = RetouchAgent(
        vision_model=vision,
        bridge=bridge,
        agent_config=agent_config,
    )

    # Progress callback
    def on_progress(record):
        r = record.result
        adj_str = ", ".join(f"{k}={v:+.1f}" if isinstance(v, float) else f"{k}={v:+d}"
                           for k, v in sorted(r.adjustments.items()))
        print(f"\n  Iteration {record.iteration + 1}:")
        print(f"    Assessment:  {r.assessment}")
        print(f"    Confidence:  {r.confidence:.2f}")
        print(f"    Converged:   {r.converged}")
        if adj_str:
            print(f"    Adjustments: {adj_str}")

    # Run
    print(f"\nInput:  {input_path}")
    print(f"Style:  {args.style}")
    print(f"Max iterations: {args.iterations}")
    print("-" * 60)

    t0 = time.time()
    result = agent.run(progress_callback=on_progress)
    elapsed = time.time() - t0

    print("\n" + "=" * 60)
    print(f"Result: {result.message}")
    print(f"Iterations: {result.iterations_run}")
    print(f"Time: {elapsed:.1f}s")

    if result.final_settings:
        print(f"\nFinal settings:")
        for k, v in sorted(result.final_settings.items()):
            if not k.startswith("_"):
                print(f"  {k}: {v}")

    # Save sidecar
    bridge.save_to_sidecar()

    # Export final image
    if args.full_res:
        print(f"\nExporting full resolution to {args.output}...")
        bridge.export_full_resolution(args.output, quality=args.quality)
    else:
        # Re-render at proxy res with final settings
        from ..engine.pixelpipe import PixelPipe
        from ..engine.modules.output import OutputModule
        pipe = PixelPipe(proxy_pixels=args.proxy)
        buf = pipe.process(str(input_path), result.final_settings)
        OutputModule.save(buf, args.output, quality=args.quality)

    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
