import numpy as np
from pathlib import Path
from PIL import Image
from dataclasses import dataclass

# Raise PIL decompression bomb limit for large images
Image.MAX_IMAGE_PIXELS = 300_000_000

TILE_SIZE = 50

PRESET_IDS = {"nature", "artworks", "space"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRESETS_DIR  = PROJECT_ROOT / "tiles" / "presets"
CACHE_DIR    = PROJECT_ROOT / "cache"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class TileIndex:
    """
    Lightweight index — loaded at startup.
    Contains ONLY rgb arrays + file paths or bin_path. No pixel data.
    """
    avg_rgbs:   np.ndarray
    tile_paths: list[Path]
    dataset_id: str
    bin_path:   Path | None = None

    @property
    def count(self) -> int:
        return len(self.avg_rgbs)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_tile_index(dataset_id: str, custom_path: Path | None = None) -> TileIndex:
    if dataset_id in PRESET_IDS:
        return _load_preset_index(dataset_id)

    if dataset_id == "custom":
        if custom_path is None:
            raise ValueError("custom_path required for custom dataset")
        return _load_custom_index(custom_path)

    raise ValueError(f"Unknown dataset_id: '{dataset_id}'")


def load_tiles_for_indices(index: TileIndex, required_indices: set[int]) -> dict[int, Image.Image]:
    """
    Load ONLY required tiles.
    Works for both bin mode and local files.
    """

    # Bin mode (Render)
    if index.bin_path and index.bin_path.exists():
        return _load_from_bin(index.bin_path, required_indices)

    # Local mode
    result = {}
    for idx in required_indices:
        if idx >= len(index.tile_paths):
            continue

        path = index.tile_paths[idx]

        try:
            img = Image.open(path).convert("RGB").resize(
                (TILE_SIZE, TILE_SIZE), Image.LANCZOS
            )
            result[idx] = img
        except Exception as e:
            print(f"[tile_utils] Failed to load {path}: {e}")
            avg = index.avg_rgbs[idx].astype(np.uint8)
            result[idx] = Image.new("RGB", (TILE_SIZE, TILE_SIZE), tuple(avg))

    return result


def _load_from_bin(bin_path: Path, required_indices: set[int]) -> dict[int, Image.Image]:
    """
    Memory-mapped tile loading from .bin file.
    Only loads required indices.
    """
    packed = np.load(bin_path, mmap_mode='r')
    result = {}

    for idx in required_indices:
        if idx >= len(packed):
            continue

        arr = packed[idx].copy()
        result[idx] = Image.fromarray(arr.astype(np.uint8), mode='RGB')

    return result


def build_and_save_cache(dataset_id: str) -> None:
    if dataset_id not in PRESET_IDS:
        raise ValueError(f"Only preset datasets supported: {dataset_id}")

    tiles_dir   = PRESETS_DIR / dataset_id
    image_paths = _get_image_paths(tiles_dir)

    if not image_paths:
        raise FileNotFoundError(f"No images found in {tiles_dir}")

    print(f"[{dataset_id}] Computing avg RGBs for {len(image_paths)} tiles...")

    avg_rgbs   = []
    batch_size = 500

    for i in range(0, len(image_paths), batch_size):
        batch      = image_paths[i:i + batch_size]
        tiles      = [_load_and_resize(p) for p in batch]
        batch_rgbs = _compute_avg_rgbs_batch(tiles)
        avg_rgbs.append(batch_rgbs)
        print(f"  Processed {min(i + batch_size, len(image_paths))}/{len(image_paths)}")

    all_rgbs = np.vstack(avg_rgbs)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(CACHE_DIR / f"{dataset_id}.npy", all_rgbs)

    filenames = [p.name for p in image_paths]
    np.save(CACHE_DIR / f"{dataset_id}_files.npy", np.array(filenames))

    print(f"[{dataset_id}] Cache saved — {len(image_paths)} tiles")


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------

def _load_preset_index(dataset_id: str) -> TileIndex:
    tiles_dir  = PRESETS_DIR / dataset_id
    cache_path = CACHE_DIR / f"{dataset_id}.npy"
    files_path = CACHE_DIR / f"{dataset_id}_files.npy"
    bin_path   = CACHE_DIR / f"{dataset_id}_tiles.bin"

    # Bin mode (Render)
    if bin_path.exists() and cache_path.exists():
        all_rgbs = np.load(cache_path)
        print(f"[{dataset_id}] Loading from packed .bin ({len(all_rgbs)} tiles)")

        return TileIndex(
            avg_rgbs=all_rgbs.astype(np.float32),
            tile_paths=[],
            dataset_id=dataset_id,
            bin_path=bin_path,
        )

    # Local mode
    image_paths = _get_image_paths(tiles_dir)

    if cache_path.exists() and files_path.exists():
        all_rgbs  = np.load(cache_path)
        all_files = np.load(files_path, allow_pickle=True).tolist()

        path_map = {p.name: p for p in image_paths}
        ordered  = [(f, r) for f, r in zip(all_files, all_rgbs) if f in path_map]

        if not ordered:
            print(f"[{dataset_id}] Cache mismatch — rebuilding")
            return _build_index_from_disk(dataset_id, image_paths)

        tile_paths = [path_map[f] for f, _ in ordered]
        avg_rgbs   = np.array([r for _, r in ordered], dtype=np.float32)

    else:
        print(f"[{dataset_id}] No cache — building index")
        return _build_index_from_disk(dataset_id, image_paths)

    print(f"[{dataset_id}] Index loaded — {len(tile_paths)} tiles")

    return TileIndex(
        avg_rgbs=avg_rgbs,
        tile_paths=tile_paths,
        dataset_id=dataset_id,
    )


def _build_index_from_disk(dataset_id: str, image_paths: list[Path]) -> TileIndex:
    print(f"[{dataset_id}] Computing RGBs for {len(image_paths)} tiles...")

    tiles    = [_load_and_resize(p) for p in image_paths]
    avg_rgbs = _compute_avg_rgbs_batch(tiles)

    return TileIndex(
        avg_rgbs=avg_rgbs,
        tile_paths=image_paths,
        dataset_id=dataset_id,
    )


def _load_custom_index(custom_path: Path) -> TileIndex:
    image_paths = _get_image_paths(custom_path)

    if not image_paths:
        raise FileNotFoundError(f"No valid images found in {custom_path}")

    print(f"[custom] Computing RGBs for {len(image_paths)} tiles...")

    tiles    = [_load_and_resize(p) for p in image_paths]
    avg_rgbs = _compute_avg_rgbs_batch(tiles)

    return TileIndex(
        avg_rgbs=avg_rgbs,
        tile_paths=image_paths,
        dataset_id="custom",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_image_paths(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    return sorted([
        p for p in directory.iterdir()
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    ])


def _load_and_resize(image_path: Path) -> Image.Image:
    return Image.open(image_path).convert("RGB").resize(
        (TILE_SIZE, TILE_SIZE), Image.LANCZOS
    )


def _compute_avg_rgbs_batch(tile_images: list[Image.Image]) -> np.ndarray:
    stacked = np.stack(
        [np.array(img, dtype=np.float32) for img in tile_images], axis=0
    )
    return stacked.mean(axis=(1, 2))