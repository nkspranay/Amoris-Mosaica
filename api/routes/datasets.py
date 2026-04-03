"""
Datasets route.

GET /api/datasets — returns available preset datasets with metadata.
"""

from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

from config import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class DatasetInfo(BaseModel):
    id:          str
    name:        str
    description: str
    tile_count:  int
    quality:     str   # "excellent" | "good" | "fair"
    cached:      bool  # Whether a pre-computed .npy cache exists


# ---------------------------------------------------------------------------
# Preset metadata
# ---------------------------------------------------------------------------

PRESET_META = {
    "nature": {
        "name":        "Nature",
        "description": "Flowers, mountains, oceans, forests, auroras and more. Wide color spectrum.",
    },
    "artworks": {
        "name":        "Famous Artworks",
        "description": "Paintings from Van Gogh, Monet, Klimt and hundreds more. Rich and expressive.",
    },
    "space": {
        "name":        "Space & NASA",
        "description": "Nebulae, galaxies, planets and deep space. Stunning darks and vivid neons.",
    },
}


# ---------------------------------------------------------------------------
# GET /api/datasets
# ---------------------------------------------------------------------------

@router.get("/datasets", response_model=list[DatasetInfo])
async def get_datasets():
    """
    Return metadata for all available preset datasets.
    Reads tile counts from the preset folders directly so
    the response always reflects what's actually on disk.
    """
    datasets = []

    for dataset_id, meta in PRESET_META.items():
        tile_count = _count_tiles(settings.presets_dir / dataset_id)
        cached     = (settings.cache_dir / f"{dataset_id}.npy").exists()
        quality    = _quality_badge(tile_count)

        datasets.append(DatasetInfo(
            id=dataset_id,
            name=meta["name"],
            description=meta["description"],
            tile_count=tile_count,
            quality=quality,
            cached=cached,
        ))

    return datasets


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _count_tiles(directory: Path) -> int:
    """Count valid image files in a preset directory."""
    if not directory.exists():
        return 0
    return sum(
        1 for p in directory.iterdir()
        if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _quality_badge(tile_count: int) -> str:
    """Return a quality badge based on tile count."""
    if tile_count >= 1000:
        return "excellent"
    if tile_count >= 500:
        return "good"
    return "fair"