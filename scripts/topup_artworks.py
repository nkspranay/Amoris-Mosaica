"""
Top-up artworks preset with pure artwork images — no frames, no digital borders.
Focuses on the painting itself, not museum/gallery photography.

Usage:
    python scripts/topup_artworks.py
"""

import asyncio
import httpx
from pathlib import Path
from PIL import Image, ImageStat
from io import BytesIO

TARGET_COUNT = 300
MIN_SIZE     = 200
OUTPUT_DIR   = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "artworks"
WIKIART_BASE = "https://www.wikiart.org"

# Styles chosen for maximum color diversity and purity of artwork
# Each style covers a different region of the color spectrum
STYLES = [
    ("fauvism",              40),   # Explosive pure colors — Matisse, Derain
    ("color-field-painting", 35),   # Pure flat color fields — great spectrum coverage
    ("abstract-expressionism",35),  # Raw emotion, vivid strokes
    ("post-impressionism",   30),   # Van Gogh, Gauguin — rich saturated colors
    ("art-nouveau",          30),   # Ornate, gold, organic curves
    ("ukiyo-e",              25),   # Japanese woodblock — flat pure colors
    ("naive-art-primitivism", 25),  # Bold, flat, vivid
    ("pointillism",          25),   # Pure dots of color — Seurat
    ("hard-edge-painting",   25),   # Geometric, flat color blocks
    ("lyrical-abstraction",  30),   # Flowing color, expressive
]

# Keywords that suggest a photo of a framed painting rather than the artwork itself
FRAME_KEYWORDS = {
    "frame", "museum", "gallery", "exhibition", "wall", "hanging",
    "display", "photo of", "photograph of", "installation"
}


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_files = set(p.stem for p in OUTPUT_DIR.glob("*.jpg"))
    existing_count = len(existing_files)
    print(f"Artworks top-up — {existing_count} images already downloaded")
    print(f"Adding up to {TARGET_COUNT} more pure artwork images\n")

    added = 0
    async with httpx.AsyncClient(
        timeout=30,
        headers={"User-Agent": "PhotoMosaicBot/1.0 (educational project)"},
        follow_redirects=True,
    ) as client:
        for style, target in STYLES:
            if added >= TARGET_COUNT:
                break
            print(f"[{style}] Fetching up to {target} images...")
            count = await _download_style(client, style, target, existing_files)
            added += count
            print(f"[{style}] Added {count} — total new: {added}/{TARGET_COUNT}\n")
            await asyncio.sleep(2)

    print(f"Done. Added {added} images. Total in folder: {existing_count + added}")


async def _download_style(client, style, limit, existing_files):
    downloaded = 0
    page = 1

    while downloaded < limit:
        try:
            url = f"{WIKIART_BASE}/en/paintings-by-style/{style}?json=2&page={page}"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"  Failed to fetch listing: {e}")
            break

        paintings = data if isinstance(data, list) else data.get("Paintings", [])
        if not paintings:
            break

        for painting in paintings:
            if downloaded >= limit:
                break

            image_url   = painting.get("image")
            painting_id = str(painting.get("id", f"art_{len(existing_files) + downloaded}"))
            title       = painting.get("title", "").lower()

            if not image_url:
                continue

            # Skip if title suggests it's a photo of a framed piece
            if any(kw in title for kw in FRAME_KEYWORDS):
                continue

            safe_id = _safe_filename(painting_id)
            if safe_id in existing_files:
                continue

            filename = OUTPUT_DIR / f"{safe_id}.jpg"
            success  = await _download_and_validate(client, image_url, filename)
            if success:
                existing_files.add(safe_id)
                downloaded += 1

            await asyncio.sleep(0.3)

        page += 1

    return downloaded


async def _download_and_validate(client, url, save_path):
    """
    Download and validate the image.
    Extra check: reject images that are mostly a single dark border color
    (indicates a framed/matted photo rather than the artwork itself).
    """
    try:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")

        if img.width < MIN_SIZE or img.height < MIN_SIZE:
            return False

        # Reject images where the border is mostly black/white (frame indicator)
        if _has_thick_border(img):
            return False

        img.save(save_path, "JPEG", quality=90)
        print(f"  ✓ {save_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ {e}")
        return False


def _has_thick_border(img: Image.Image, border_pct: float = 0.05) -> bool:
    """
    Returns True if the image has a thick uniform border (likely a frame).
    Samples the outermost 5% of pixels and checks if they're near-black or near-white.
    """
    w, h   = img.size
    border = max(5, int(min(w, h) * border_pct))

    edges = [
        img.crop((0, 0, w, border)),           # top
        img.crop((0, h - border, w, h)),        # bottom
        img.crop((0, 0, border, h)),            # left
        img.crop((w - border, 0, w, h)),        # right
    ]

    for edge in edges:
        stat = ImageStat.Stat(edge)
        mean = sum(stat.mean) / 3  # average brightness across RGB
        stddev = sum(stat.stddev) / 3

        # Near-black or near-white border with very low variance = frame
        if (mean < 20 or mean > 235) and stddev < 15:
            return True

    return False


def _safe_filename(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


if __name__ == "__main__":
    asyncio.run(main())