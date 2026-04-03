import sys
import json
import numpy as np
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tiles.tile_utils import (
    TILE_SIZE, PRESET_IDS,
    PRESETS_DIR, CACHE_DIR,
    SUPPORTED_EXTENSIONS,
)


def pack_dataset(dataset_id: str) -> dict:
    tiles_dir  = PRESETS_DIR / dataset_id
    cache_path = CACHE_DIR / f"{dataset_id}.npy"
    files_path = CACHE_DIR / f"{dataset_id}_files.npy"
    bin_path   = CACHE_DIR / f"{dataset_id}_tiles.bin"

    if not tiles_dir.exists():
        raise FileNotFoundError(f"Preset folder not found: {tiles_dir}")

    if not cache_path.exists() or not files_path.exists():
        raise FileNotFoundError(
            f"Cache not found for {dataset_id}. "
            f"Run scripts/precompute_caches.py first."
        )

    # Load file order
    all_files = np.load(files_path, allow_pickle=True).tolist()

    path_map = {
        p.name: p for p in tiles_dir.iterdir()
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    }

    valid = [(f, path_map[f]) for f in all_files if f in path_map]

    if not valid:
        raise FileNotFoundError(f"No matching images found for {dataset_id}")

    print(f"[{dataset_id}] Packing {len(valid)} tiles → {bin_path.name}")

    # Pre-allocate (avoids RAM spike)
    packed = np.zeros(
        (len(valid), TILE_SIZE, TILE_SIZE, 3),
        dtype=np.uint8
    )

    failed = 0
    write_idx = 0

    for i, (fname, fpath) in enumerate(valid):
        try:
            img = Image.open(fpath).convert("RGB").resize(
                (TILE_SIZE, TILE_SIZE), Image.LANCZOS
            )

            packed[write_idx] = np.array(img, dtype=np.uint8)
            write_idx += 1

        except Exception as e:
            print(f"  Failed {fname}: {e}")
            failed += 1

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(valid)}...")

    if write_idx == 0:
        raise RuntimeError(f"No tiles could be loaded for {dataset_id}")

    # Trim if failures occurred
    packed = packed[:write_idx]

    # -------- CRITICAL FIX --------
    # Save as .npy first, then rename to .bin
    tmp_path = bin_path.with_suffix(".npy")
    np.save(tmp_path, packed)
    tmp_path.replace(bin_path)
    # --------------------------------

    size_mb = bin_path.stat().st_size / (1024 * 1024)

    print(f"  Packed {write_idx} tiles ({size_mb:.1f}MB) → {bin_path.name}")
    if failed:
        print(f"  {failed} tiles failed and were skipped")

    return {
        "dataset_id": dataset_id,
        "tile_count": write_idx,
        "tile_size":  TILE_SIZE,
        "size_mb":    round(size_mb, 2),
        "bin_file":   bin_path.name,
    }


def main():
    print("=" * 55)
    print("Packing preset tiles for deployment")
    print("=" * 55)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    metadata = {}
    total_mb = 0

    for dataset_id in sorted(PRESET_IDS):
        print(f"\n── {dataset_id} ──")
        try:
            info = pack_dataset(dataset_id)
            metadata[dataset_id] = info
            total_mb += info["size_mb"]
        except Exception as e:
            print(f"  Failed: {e}")

    # Save metadata
    meta_path = CACHE_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print("\n" + "=" * 55)
    print(f"Done. Total size: {total_mb:.1f}MB")
    print(f"Metadata saved → {meta_path}")
    print("\nCommit cache/:")
    print("  git add cache/")
    print("  git commit -m 'Add packed tile caches'")
    print("=" * 55)


if __name__ == "__main__":
    main()