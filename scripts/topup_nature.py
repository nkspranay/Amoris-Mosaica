"""
Top-up nature preset with vibrant, diverse, edge-case-covering images.
Focuses on: snowy scenes, auroras, night skies, flowers, sunsets, waterfalls,
lush greens — to handle the full brightness/darkness/color spectrum.

Usage:
    python scripts/topup_nature.py
"""

import asyncio
import httpx
import os
from pathlib import Path
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
TARGET_COUNT        = 300
MIN_SIZE            = 200
OUTPUT_DIR          = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "nature"
UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"

# Each query is chosen to cover a specific edge case or color region
# that the original download may have missed
SEARCH_QUERIES = [
    # Dark edge cases
    ("aurora borealis night",    30),   # Deep blacks + vivid green/purple
    ("starry night sky",         25),   # Near-black with star whites
    ("milky way landscape",      25),   # Dark gradient with color band
    ("bioluminescent ocean",     20),   # Dark + electric blue/teal

    # Light/white edge cases
    ("snowy mountain",           25),   # Pure whites, cold blues
    ("white sand beach",         20),   # Bright whites, warm tones
    ("snow covered forest",      20),   # White + muted greens
    ("blizzard",                 15),   # Near-white scenes

    # Vibrant color spectrum
    ("tulip field",              25),   # Mass of pure vivid color
    ("wildflower meadow",        25),   # Diverse natural colors
    ("cherry blossom",           20),   # Soft pinks, whites
    ("sunflower field",          20),   # Pure yellows
    ("lavender field purple",    20),   # Deep purples

    # Sunset/golden hour (warm spectrum)
    ("golden hour landscape",    25),   # Warm oranges, golds
    ("dramatic sunset sky",      25),   # Reds, oranges, purples
    ("sunrise mountain fog",     20),   # Soft warm pinks

    # Water and greens
    ("waterfall jungle",         20),   # Vivid greens, whites
    ("lush rainforest",          20),   # Deep saturated greens
    ("turquoise lake mountain",  20),   # Vivid teals + rock grays
    ("green valley aerial",      15),   # Aerial green landscapes

    # Interesting skies
    ("stormy dramatic sky",      20),   # Dark grays, dynamic
    ("rainbow landscape",        15),   # Full spectrum in one shot
    ("colorful hot air balloon", 15),   # Vivid colors against sky
]


async def main() -> None:
    if not UNSPLASH_ACCESS_KEY:
        print("ERROR: UNSPLASH_ACCESS_KEY not set in .env")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_files = set(p.stem for p in OUTPUT_DIR.glob("*.jpg"))
    existing_count = len(existing_files)
    print(f"Nature top-up — {existing_count} images already downloaded")
    print(f"Adding up to {TARGET_COUNT} more vibrant/diverse nature images\n")

    added = 0
    async with httpx.AsyncClient(
        timeout=30,
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
    ) as client:
        for query, target in SEARCH_QUERIES:
            if added >= TARGET_COUNT:
                break
            print(f"[{query}] Fetching up to {target} images...")
            count = await _download_query(client, query, target, existing_files)
            added += count
            print(f"[{query}] Added {count} — total new: {added}/{TARGET_COUNT}\n")
            await asyncio.sleep(1.5)

    print(f"Done. Added {added} images. Total in folder: {existing_count + added}")


async def _download_query(client, query, limit, existing_files):
    downloaded = 0
    page = 1

    while downloaded < limit:
        try:
            response = await client.get(UNSPLASH_SEARCH_URL, params={
                "query":       query,
                "per_page":    30,
                "page":        page,
                "orientation": "squarish",
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

            url      = photo.get("urls", {}).get("small")
            photo_id = photo.get("id", f"nature_{len(existing_files) + downloaded}")

            if not url or photo_id in existing_files:
                continue

            filename = OUTPUT_DIR / f"{photo_id}.jpg"
            success  = await _download_image(client, url, filename)
            if success:
                existing_files.add(photo_id)
                downloaded += 1

        page += 1
        await asyncio.sleep(0.5)

    return downloaded


async def _download_image(client, url, save_path):
    try:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        if img.width < MIN_SIZE or img.height < MIN_SIZE:
            return False
        img.save(save_path, "JPEG", quality=90)
        print(f"  ✓ {save_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())