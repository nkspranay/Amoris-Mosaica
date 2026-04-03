"""
Download ~500 nature images into tiles/presets/nature/
Uses Unsplash API with diverse queries to guarantee full color spectrum coverage.

Usage:
    python scripts/download_nature.py

Requires:
    UNSPLASH_ACCESS_KEY in .env
    pip install httpx python-dotenv Pillow
"""

import asyncio
import httpx
import os
from pathlib import Path
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
TARGET_COUNT        = 500
MIN_SIZE            = 200
OUTPUT_DIR          = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "nature"

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

# Diverse queries — each targets a different region of the color spectrum
# Red/orange/yellow → flowers, autumn, desert, sunset
# Green             → forest, jungle, moss
# Blue/cyan         → ocean, glacier, waterfall
# White/gray        → snow, fog, clouds
# Brown/earth       → desert sand, canyon, terrain
SEARCH_QUERIES = [
    ("flowers",        40),   # reds, pinks, yellows, purples
    ("autumn forest",  35),   # oranges, reds, browns
    ("desert",         35),   # warm oranges, yellows, earth tones
    ("sunset",         35),   # warm gradient spectrum
    ("coral reef",     35),   # vivid blues, oranges, pinks
    ("ocean waves",    35),   # deep blues, teals, whites
    ("glacier",        30),   # cool blues, whites, cyans
    ("waterfall",      30),   # greens, blues
    ("tropical",       30),   # vivid greens, blues
    ("snow mountain",  30),   # whites, grays, cold blues
    ("moss forest",    25),   # deep greens
    ("lavender field", 25),   # purples
    ("volcanic",       25),   # dark grays, reds, oranges
    ("canyon",         25),   # earth reds, browns
    ("lightning",      25),   # dark backgrounds, electric whites/purples
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    if not UNSPLASH_ACCESS_KEY:
        print("ERROR: UNSPLASH_ACCESS_KEY not set in .env")
        print("Get a free key at https://unsplash.com/developers")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = len(list(OUTPUT_DIR.glob("*.jpg")))
    print(f"Starting Unsplash nature download — {existing} images already in folder")
    print(f"Target: {TARGET_COUNT} images\n")

    downloaded = existing
    async with httpx.AsyncClient(timeout=30, headers={
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
    }) as client:
        for query, target in SEARCH_QUERIES:
            if downloaded >= TARGET_COUNT:
                break

            print(f"[{query}] Fetching up to {target} images...")
            count = await _download_query(client, query, target, downloaded)
            downloaded += count
            print(f"[{query}] Got {count} — total: {downloaded}/{TARGET_COUNT}\n")

            # Unsplash rate limit: 50 requests/hour on free tier — small delay
            await asyncio.sleep(1.5)

    print(f"Done. {downloaded} images saved to {OUTPUT_DIR}")


async def _download_query(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
    start_index: int,
) -> int:
    """Paginate through Unsplash search results and download images."""
    downloaded = 0
    page = 1
    per_page = min(30, limit)

    while downloaded < limit:
        try:
            response = await client.get(UNSPLASH_SEARCH_URL, params={
                "query":    query,
                "per_page": per_page,
                "page":     page,
                "orientation": "squarish",  # square-ish images tile better
            })
            response.raise_for_status()
            results = response.json().get("results", [])
        except Exception as e:
            print(f"  Search failed (page {page}): {e}")
            break

        if not results:
            break

        for photo in results:
            if downloaded >= limit:
                break

            # Use "small" size — good quality, faster download, ~400px
            url = photo.get("urls", {}).get("small")
            if not url:
                continue

            photo_id = photo.get("id", f"unsplash_{start_index + downloaded}")
            filename  = OUTPUT_DIR / f"{photo_id}.jpg"

            if filename.exists():
                downloaded += 1
                continue

            success = await _download_image(client, url, filename)
            if success:
                downloaded += 1

        page += 1
        await asyncio.sleep(0.5)

    return downloaded


async def _download_image(
    client: httpx.AsyncClient,
    url: str,
    save_path: Path,
) -> bool:
    """Download a single image, validate, save as JPEG."""
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGB")

        if img.width < MIN_SIZE or img.height < MIN_SIZE:
            return False

        img.save(save_path, "JPEG", quality=90)
        print(f"  ✓ {save_path.name}")
        return True

    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())