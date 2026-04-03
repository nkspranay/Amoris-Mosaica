"""
CLI entry point for photo mosaic generation.

Usage:
    python -m cli.main --image path/to/image.jpg --dataset nature --quality 2
    python -m cli.main --prompt "mount everest" --dataset space --quality 3
    python -m cli.main --image photo.jpg --dataset custom --tiles path/to/tiles/

Options:
    --image     Path to target image
    --prompt    Text prompt (fetches image from Unsplash/Pixabay)
    --dataset   Preset dataset: nature | artworks | space | custom
    --tiles     Path to custom tile directory (required if dataset=custom)
    --quality   1 (low) | 2 (medium) | 3 (high). Default: 2
    --output    Output file path. Default: mosaic.png
"""

import asyncio
import argparse
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:

    # --- Lazy imports so CLI starts fast ---
    from input.resolver import resolve_input, cleanup_temp
    from engine.mosaic import generate_mosaic, MosaicRequest
    from validators import validate_quality, validate_dataset_id

    # --- Validate ---
    quality_result = validate_quality(args.quality)
    if not quality_result.valid:
        print(f"Error: {quality_result.error}")
        sys.exit(1)

    dataset_result = validate_dataset_id(args.dataset)
    if not dataset_result.valid:
        print(f"Error: {dataset_result.error}")
        sys.exit(1)

    if args.dataset == "custom" and not args.tiles:
        print("Error: --tiles is required when using --dataset custom")
        sys.exit(1)

    if not args.image and not args.prompt:
        print("Error: provide either --image or --prompt")
        sys.exit(1)

    if args.image and args.prompt:
        print("Error: provide either --image or --prompt, not both")
        sys.exit(1)

    # --- Resolve input ---
    print("\nResolving input...")
    try:
        resolved = await resolve_input(
            uploaded_path=Path(args.image) if args.image else None,
            prompt=args.prompt,
        )
    except Exception as e:
        print(f"Error resolving input: {e}")
        sys.exit(1)

    # --- Build request ---
    custom_tiles_path = Path(args.tiles) if args.tiles else None

    request = MosaicRequest(
        target_image_path=resolved.image_path,
        dataset_id=args.dataset,
        quality=args.quality,
        session_id="cli",
        custom_tiles_path=custom_tiles_path,
    )

    # --- Progress printer ---
    last_stage = None

    async def cli_progress(stage: str, percent: int, eta_ms=None) -> None:
        nonlocal last_stage
        if stage != last_stage:
            print(f"\n[{stage}]", end=" ", flush=True)
            last_stage = stage
        bar = _progress_bar(percent)
        eta = f" — ETA {eta_ms // 1000}s" if eta_ms else ""
        print(f"\r[{stage}] {bar} {percent}%{eta}", end="", flush=True)

    # --- Generate ---
    print("Starting mosaic generation...")
    try:
        result = await generate_mosaic(request, emit=cli_progress)
    except Exception as e:
        print(f"\nError during generation: {e}")
        cleanup_temp(resolved)
        sys.exit(1)
    finally:
        cleanup_temp(resolved)

    # --- Save output ---
    output_path = Path(args.output)
    result.output_image.save(output_path, format="PNG")

    print(f"\n\nDone.")
    print(f"  Output   : {output_path.resolve()}")
    print(f"  Tiles    : {result.tile_count}")
    print(f"  Grid     : {result.grid_width} × {result.grid_height}")
    print(f"  Time     : {result.processing_ms}ms")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress_bar(percent: int, width: int = 30) -> str:
    filled = int(width * percent / 100)
    return f"[{'█' * filled}{'░' * (width - filled)}]"


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a photo mosaic from an image or text prompt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--image",   type=str, help="Path to target image")
    parser.add_argument("--prompt",  type=str, help="Text prompt for image fetch")
    parser.add_argument("--dataset", type=str, required=True,
                        choices=["nature", "artworks", "space", "custom"],
                        help="Tile dataset to use")
    parser.add_argument("--tiles",   type=str,
                        help="Path to custom tile directory (required if dataset=custom)")
    parser.add_argument("--quality", type=int, default=2, choices=[1, 2, 3],
                        help="Quality level: 1=low, 2=medium, 3=high (default: 2)")
    parser.add_argument("--output",  type=str, default="mosaic.png",
                        help="Output file path (default: mosaic.png)")
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(run(args))