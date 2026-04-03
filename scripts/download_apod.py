"""
Download NASA APOD (Astronomy Picture of the Day) archive.
Every image is handpicked by NASA astronomers — highest quality space images.
~10,000 images since 1995, all public domain.

Usage:
    python scripts/download_apod.py

Requires:
    NASA_API_KEY in .env (or uses DEMO_KEY — 30 req/hr)
"""

import asyncio
import httpx
import os
from pathlib import Path
from PIL import Image
from io import BytesIO
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
TARGET_COUNT = 2000
MIN_SIZE     = 200
OUTPUT_DIR   = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "space"
APOD_URL     = "https://api.nasa.gov/planetary/apod"

# Date range — APOD started June 16, 1995
START_DATE = date(1995, 6, 16)
END_DATE   = date.today()


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = set(p.stem for p in OUTPUT_DIR.glob("*.jpg"))
    print(f"APOD download — {len(existing)} images already in space folder")
    print(f"Target: {TARGET_COUNT} more images\n")

    if NASA_API_KEY == "DEMO_KEY":
        print("Warning: DEMO_KEY limits to 30 req/hr. Get a free key at api.nasa.gov\n")

    added = 0
    # Fetch in batches of 100 (APOD API max per request)
    batch_size  = 100
    current_end = END_DATE

    async with httpx.AsyncClient(timeout=30) as client:
        while added < TARGET_COUNT:
            current_start = current_end - timedelta(days=batch_size)
            if current_start < START_DATE:
                current_start = START_DATE

            print(f"Fetching {current_start} → {current_end}...")

            try:
                response = await client.get(APOD_URL, params={
                    "api_key":   NASA_API_KEY,
                    "start_date": current_start.isoformat(),
                    "end_date":   current_end.isoformat(),
                    "thumbs":     True,
                })
                response.raise_for_status()
                entries = response.json()
            except Exception as e:
                print(f"  Fetch failed: {e}")
                await asyncio.sleep(5)
                current_end = current_start
                continue

            for entry in entries:
                if added >= TARGET_COUNT:
                    break

                # Only download actual images, not videos
                if entry.get("media_type") != "image":
                    continue

                # Use HD URL if available, fall back to regular
                url     = entry.get("hdurl") or entry.get("url")
                apod_id = f"apod_{entry.get('date', 'unknown').replace('-', '')}"

                if not url or apod_id in existing:
                    continue

                filename = OUTPUT_DIR / f"{apod_id}.jpg"
                success  = await _download_image(client, url, filename)
                if success:
                    existing.add(apod_id)
                    added += 1

                await asyncio.sleep(0.2)

            print(f"  Added so far: {added}/{TARGET_COUNT}")
            current_end = current_start - timedelta(days=1)

            if current_end < START_DATE:
                print("Reached beginning of APOD archive.")
                break

            await asyncio.sleep(1)

    print(f"\nDone. Added {added} APOD images to space preset.")


async def _download_image(client, url, save_path):
    try:
        r = await client.get(url, follow_redirects=True, timeout=30)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        if img.width < MIN_SIZE or img.height < MIN_SIZE:
            return False
        img.save(save_path, "JPEG", quality=92)
        print(f"  ✓ {save_path.name}")
        return True
    except Exception as e:
        print(f"  ✗ {url[:60]}: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(main())