"""
Top-up space preset with focused astronomical subjects.
No human-made objects, no humans — pure deep space only.

Usage:
    python scripts/topup_space.py
"""

import asyncio
import httpx
import os
from pathlib import Path
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

NASA_API_KEY  = os.getenv("NASA_API_KEY", "DEMO_KEY")
TARGET_COUNT  = 300        # How many MORE images to add
MIN_SIZE      = 200
OUTPUT_DIR    = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "space"
NASA_SEARCH_URL = "https://images-api.nasa.gov/search"

# Focused purely on natural astronomical phenomena
# Deliberately excludes: astronauts, ISS, rockets, shuttles, satellites
SEARCH_QUERIES = [
    ("nebula",              30),
    ("galaxy",              30),
    ("star cluster",        25),
    ("supernova remnant",   25),
    ("pulsar",              20),
    ("quasar",              20),
    ("black hole",          20),
    ("asteroid",            20),
    ("comet",               20),
    ("hypernova",           15),
    ("deep field galaxy",   15),
    ("planetary nebula",    20),
    ("stellar nursery",     20),
    ("globular cluster",    20),
    ("interstellar",        15),
    ("cosmic dust",         15),
]

# Keywords to filter OUT — skip any image whose title/description contains these
EXCLUDE_KEYWORDS = {
    "astronaut", "shuttle", "rocket", "iss", "station", "launch",
    "spacecraft", "satellite", "hubble repair", "crew", "spacewalk",
    "mission control", "engineer", "scientist", "people", "person",
}


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_files = set(p.stem for p in OUTPUT_DIR.glob("*.jpg"))
    existing_count = len(existing_files)
    print(f"Space top-up — {existing_count} images already downloaded")
    print(f"Adding up to {TARGET_COUNT} more focused astronomical images\n")

    added = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for query, target in SEARCH_QUERIES:
            if added >= TARGET_COUNT:
                break
            print(f"[{query}] Fetching up to {target} images...")
            count = await _download_query(client, query, target, existing_files)
            added += count
            print(f"[{query}] Added {count} — total new: {added}/{TARGET_COUNT}\n")
            await asyncio.sleep(1)

    print(f"Done. Added {added} images. Total in folder: {existing_count + added}")


async def _download_query(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
    existing_files: set,
) -> int:
    try:
        response = await client.get(NASA_SEARCH_URL, params={
            "q": query,
            "media_type": "image",
            "page_size": min(limit * 3, 100),
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

        # Filter out human-made objects
        data = item.get("data", [{}])[0]
        title = (data.get("title", "") + " " + data.get("description", "")).lower()
        if any(kw in title for kw in EXCLUDE_KEYWORDS):
            continue

        links = item.get("links", [])
        image_url = next(
            (l["href"] for l in links if l.get("render") == "image"), None
        )
        if not image_url:
            continue

        nasa_id = data.get("nasa_id", f"space_{len(existing_files) + downloaded}")
        safe_id = _safe_filename(str(nasa_id))

        if safe_id in existing_files:
            continue

        filename = OUTPUT_DIR / f"{safe_id}.jpg"
        success = await _download_image(client, image_url, filename)
        if success:
            existing_files.add(safe_id)
            downloaded += 1

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


def _safe_filename(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


if __name__ == "__main__":
    if NASA_API_KEY == "DEMO_KEY":
        print("Warning: using DEMO_KEY — limited to 30 requests/hour\n")
    asyncio.run(main())
    