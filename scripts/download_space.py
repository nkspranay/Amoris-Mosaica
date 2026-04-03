"""
Download ~500 space/NASA images into tiles/presets/space/

Usage:
    python scripts/download_space.py

Requires:
    NASA_API_KEY in .env or set directly in the script below
    pip install httpx python-dotenv Pillow
"""

import asyncio
import httpx
import os
import sys
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NASA_API_KEY  = os.getenv("NASA_API_KEY", "DEMO_KEY")  # DEMO_KEY = 30 req/hr
TARGET_COUNT  = 500
MIN_SIZE      = 200        # Skip images smaller than 200×200
OUTPUT_DIR    = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "space"

# Search queries — diverse range to cover full color spectrum
SEARCH_QUERIES = [
    "nebula",
    "galaxy",
    "planet",
    "earth from space",
    "supernova",
    "jupiter",
    "saturn",
    "solar flare",
    "moon surface",
    "mars",
    "aurora",
    "star cluster",
    "black hole",
    "comet",
    "deep space",
]

NASA_SEARCH_URL = "https://images-api.nasa.gov/search"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = len(list(OUTPUT_DIR.glob("*.jpg")))
    print(f"Starting NASA download — {existing} images already in folder")
    print(f"Target: {TARGET_COUNT} images\n")

    downloaded = existing
    async with httpx.AsyncClient(timeout=30) as client:
        for query in SEARCH_QUERIES:
            if downloaded >= TARGET_COUNT:
                break

            per_query = (TARGET_COUNT - downloaded) // max(1, len(SEARCH_QUERIES) - SEARCH_QUERIES.index(query))
            per_query = max(10, min(per_query, 50))

            print(f"[{query}] Fetching up to {per_query} images...")
            count = await _download_query(client, query, per_query, downloaded)
            downloaded += count
            print(f"[{query}] Got {count} images — total: {downloaded}/{TARGET_COUNT}\n")

    print(f"Done. {downloaded} images saved to {OUTPUT_DIR}")


async def _download_query(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
    already_have: int,
) -> int:
    """Search NASA API for a query and download up to limit images."""
    try:
        response = await client.get(NASA_SEARCH_URL, params={
            "q": query,
            "media_type": "image",
            "page_size": min(limit * 2, 100),  # over-fetch to account for failures
        })
        response.raise_for_status()
        items = response.json().get("collection", {}).get("items", [])
    except Exception as e:
        print(f"  Search failed: {e}")
        return 0

    downloaded = 0
    for item in items:
        if downloaded >= limit:
            break

        links = item.get("links", [])
        image_url = next(
            (l["href"] for l in links if l.get("render") == "image"),
            None,
        )
        if not image_url:
            continue

        # Use NASA ID as filename for uniqueness
        nasa_id = item.get("data", [{}])[0].get("nasa_id", f"nasa_{already_have + downloaded}")
        filename = OUTPUT_DIR / f"{_safe_filename(nasa_id)}.jpg"

        if filename.exists():
            downloaded += 1
            continue

        success = await _download_image(client, image_url, filename)
        if success:
            downloaded += 1

    return downloaded


async def _download_image(
    client: httpx.AsyncClient,
    url: str,
    save_path: Path,
) -> bool:
    """Download a single image, validate it, save as JPEG."""
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

        # Validate it's a real image and meets minimum size
        from io import BytesIO
        img = Image.open(BytesIO(response.content)).convert("RGB")

        if img.width < MIN_SIZE or img.height < MIN_SIZE:
            return False

        img.save(save_path, "JPEG", quality=90)
        print(f"  ✓ {save_path.name}")
        return True

    except Exception as e:
        print(f"  ✗ Failed ({url[:60]}...): {e}")
        return False


def _safe_filename(name: str) -> str:
    """Strip characters that are invalid in filenames."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if NASA_API_KEY == "DEMO_KEY":
        print("Warning: using DEMO_KEY — limited to 30 requests/hour.")
        print("Set NASA_API_KEY in your .env for better rate limits.\n")

    asyncio.run(main())
    