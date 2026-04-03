"""
Pre-compute and save avg RGB caches for all three preset tile datasets.

Run this once after downloading preset images, and again any time
the preset folders are updated.

Usage:
    python scripts/precompute_caches.py

Output:
    cache/nature.npy
    cache/artworks.npy
    cache/space.npy
"""

import sys
from pathlib import Path

# Make sure project root is on the path so we can import our modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tiles.tile_utils import build_and_save_cache, PRESET_IDS


def main() -> None:
    print("=" * 50)
    print("Pre-computing RGB caches for preset datasets")
    print("=" * 50 + "\n")

    failed = []

    for dataset_id in sorted(PRESET_IDS):
        print(f"Processing: {dataset_id}")
        print("-" * 30)
        try:
            build_and_save_cache(dataset_id)
            print(f"✓ {dataset_id} cache complete\n")
        except FileNotFoundError as e:
            print(f"✗ Skipping {dataset_id} — {e}\n")
            failed.append(dataset_id)
        except Exception as e:
            print(f"✗ Failed {dataset_id} — {e}\n")
            failed.append(dataset_id)

    print("=" * 50)
    succeeded = sorted(PRESET_IDS - set(failed))

    if succeeded:
        print(f"Done. Caches built for: {', '.join(succeeded)}")
        print(f"Files saved to: {PROJECT_ROOT / 'cache'}/")

    if failed:
        print(f"Skipped (no images yet): {', '.join(failed)}")
        print("Run the download scripts first, then re-run this script.")

    print("=" * 50)


if __name__ == "__main__":
    main()
    