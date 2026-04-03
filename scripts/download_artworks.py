"""
Download ~500 famous artwork images into tiles/presets/artworks/
Uses WikiArt's public API — no key required.

Usage:
    python scripts/download_artworks.py

Requires:
    pip install httpx Pillow
"""

import asyncio
import httpx
import json
from pathlib import Path
from PIL import Image
from io import BytesIO

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TARGET_COUNT = 500
MIN_SIZE     = 200
OUTPUT_DIR   = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "artworks"

WIKIART_BASE = "https://www.wikiart.org"

# Art styles — each has wildly different color palettes
# Impressionism    → soft pastels, outdoor light
# Expressionism    → vivid, emotional, high contrast
# Surrealism       → dreamlike, unusual color combos
# Abstract         → pure color fields — great for spectrum coverage
# Baroque          → deep shadows, rich golds
# Romanticism      → dramatic lighting, landscapes
# Pop Art          → flat bright colors
# Cubism           → geometric, varied tones
# Renaissance      → warm skin tones, religious golds
# Japanese art     → minimalist, ink blacks, nature colors
STYLES = [
    ("impressionism",   55),
    ("expressionism",   55),
    ("surrealism",      50),
    ("abstract-art",    50),
    ("baroque",         45),
    ("romanticism",     45),
    ("pop-art",         40),
    ("cubism",          40),
    ("high-renaissance",35),
    ("japanese-art",    35),
    ("minimalism",      30),
    ("symbolism",       20),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = len(list(OUTPUT_DIR.glob("*.jpg")))
    print(f"Starting WikiArt download — {existing} images already in folder")
    print(f"Target: {TARGET_COUNT} images\n")

    downloaded = existing
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "PhotoMosaicBot/1.0 (educational project)"},
        follow_redirects=True,
    ) as client:
        for style, target in STYLES:
            if downloaded >= TARGET_COUNT:
                break

            print(f"[{style}] Fetching up to {target} images...")
            count = await _download_style(client, style, target, downloaded)
            downloaded += count
            print(f"[{style}] Got {count} — total: {downloaded}/{TARGET_COUNT}\n")

            await asyncio.sleep(2)  # Be polite to WikiArt servers

    print(f"Done. {downloaded} images saved to {OUTPUT_DIR}")


async def _download_style(
    client: httpx.AsyncClient,
    style: str,
    limit: int,
    start_index: int,
) -> int:
    """Fetch painting list for a style and download images."""
    downloaded = 0
    page = 1

    while downloaded < limit:
        try:
            # WikiArt's public JSON API for painting lists by style
            url = f"{WIKIART_BASE}/en/paintings-by-style/{style}?json=2&page={page}"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"  Failed to fetch listing (page {page}): {e}")
            break

        paintings = data if isinstance(data, list) else data.get("Paintings", [])
        if not paintings:
            break

        for painting in paintings:
            if downloaded >= limit:
                break

            image_url = painting.get("image")
            painting_id = painting.get("id", f"art_{start_index + downloaded}")

            if not image_url:
                continue

            filename = OUTPUT_DIR / f"{_safe_filename(str(painting_id))}.jpg"
            if filename.exists():
                downloaded += 1
                continue

            success = await _download_image(client, image_url, filename)
            if success:
                downloaded += 1

            await asyncio.sleep(0.3)  # Polite delay per image

        page += 1

    return downloaded


async def _download_image(
    client: httpx.AsyncClient,
    url: str,
    save_path: Path,
) -> bool:
    """Download a single artwork image, validate, save as JPEG."""
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


def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())