"""CLI entry point: python -m lightpilot.engine photo.ARW --output result.jpg

Processes a RAW (or standard) image through the PixelPipe and writes
the result to disk.  Supports editing parameters via --params JSON
or from a sidecar file.
"""

import argparse
import json
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lightpilot.engine",
        description="LightPilot PixelPipe — RAW processing engine",
    )
    parser.add_argument("input", help="Input image file (RAW or JPEG/TIFF/PNG)")
    parser.add_argument(
        "--output", "-o", required=True,
        help="Output file path (.jpg, .tiff, .png)",
    )
    parser.add_argument(
        "--params", "-p", type=str, default=None,
        help='JSON string of parameters, e.g. \'{"Exposure2012": 1.0}\'',
    )
    parser.add_argument(
        "--sidecar", "-s", action="store_true",
        help="Load parameters from the image's sidecar file",
    )
    parser.add_argument(
        "--proxy", type=int, default=2_000_000,
        help="Proxy resolution in pixels (0 = full res, default 2000000)",
    )
    parser.add_argument(
        "--quality", "-q", type=int, default=95,
        help="JPEG quality 1–100 (default 95)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print per-module timing",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    # --- Collect parameters ---
    params: dict = {}

    if args.sidecar:
        from ..catalog.sidecar import load as load_sidecar
        params = load_sidecar(input_path)
        print(f"Loaded {len(params)} params from sidecar")

    if args.params:
        try:
            user_params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON in --params: {e}")
            sys.exit(1)
        params.update(user_params)

    print(f"Input:  {input_path}")
    print(f"Output: {args.output}")
    if params:
        print(f"Params: {json.dumps(params, indent=2)}")

    # --- Run pipeline ---
    from .pixelpipe import PixelPipe

    pipe = PixelPipe(proxy_pixels=args.proxy)

    t0 = time.time()
    buf = pipe.process_and_save(
        str(input_path), args.output, params,
        quality=args.quality, verbose=args.verbose,
    )
    elapsed = time.time() - t0

    print(f"Done in {elapsed:.2f}s — {buf.width}x{buf.height} → {args.output}")


if __name__ == "__main__":
    main()
