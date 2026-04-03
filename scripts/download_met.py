"""
Download artworks from The Metropolitan Museum of Art Open Access collection.
400,000+ public domain artworks, completely free, no API key needed.

Usage:
    python scripts/download_met.py

API docs: https://metmuseum.github.io/
"""

import asyncio
import httpx
import random
from pathlib import Path
from PIL import Image
from io import BytesIO

TARGET_COUNT = 2000
MIN_SIZE     = 200
OUTPUT_DIR   = Path(__file__).resolve().parent.parent / "tiles" / "presets" / "artworks"
MET_BASE     = "https://collectionapi.metmuseum.org/public/collection/v1"

# Departments with the best color diversity for mosaic tiles
# Each tuple: (department name for logging, department ID)
DEPARTMENTS = [
    ("European Paintings",          11),   # Oil paintings — rich color range
    ("Asian Art",                   6),    # Woodblocks, ink paintings — unique palette
    ("The American Wing",           1),    # American paintings — landscapes, portraits
    ("Egyptian Art",                10),   # Gold, earth tones, hieroglyphics
    ("Islamic Art",                 14),   # Geometric patterns, vivid blues/golds
    ("Greek and Roman Art",         13),   # Classical forms, terracotta
    ("Modern and Contemporary Art", 21),   # Abstract, vivid, diverse
    ("Drawings and Prints",         9),    # High contrast, varied styles
    ("Photographs",                 19),   # B&W and color photography
    ("Musical Instruments",         18),   # Rich woods, metals, varied textures
]

# Target per department — spread evenly
PER_DEPARTMENT = TARGET_COUNT // len(DEPARTMENTS) + 50


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = set(p.stem for p in OUTPUT_DIR.glob("*.jpg"))
    print(f"Met Museum download — {len(existing)} images already in artworks folder")
    print(f"Target: {TARGET_COUNT} more images\n")

    added = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for dept_name, dept_id in DEPARTMENTS:
            if added >= TARGET_COUNT:
                break

            print(f"[{dept_name}] Fetching object IDs...")
            object_ids = await _get_department_objects(client, dept_id)

            if not object_ids:
                print(f"  No objects found for {dept_name}")
                continue

            # Shuffle so we get variety, not just the first N
            random.shuffle(object_ids)
            print(f"  Found {len(object_ids)} objects — downloading up to {PER_DEPARTMENT}")

            dept_added = 0
            for obj_id in object_ids:
                if added >= TARGET_COUNT or dept_added >= PER_DEPARTMENT:
                    break

                obj_key = f"met_{obj_id}"
                if obj_key in existing:
                    dept_added += 1
                    continue

                image_url = await _get_primary_image(client, obj_id)
                if not image_url:
                    continue

                filename = OUTPUT_DIR / f"{obj_key}.jpg"
                success  = await _download_image(client, image_url, filename)
                if success:
                    existing.add(obj_key)
                    added += 1
                    dept_added += 1

                await asyncio.sleep(0.15)

            print(f"  [{dept_name}] Added {dept_added} — total: {added}/{TARGET_COUNT}\n")

    print(f"Done. Added {added} Met Museum artworks.")


async def _get_department_objects(client, dept_id: int) -> list[int]:
    """Fetch all object IDs for a department that have images."""
    try:
        r = await client.get(f"{MET_BASE}/objects", params={
            "departmentIds": dept_id,
            "hasImages":     True,
        })
        r.raise_for_status()
        return r.json().get("objectIDs", []) or []
    except Exception as e:
        print(f"  Failed to fetch dept {dept_id}: {e}")
        return []


async def _get_primary_image(client, object_id: int) -> str | None:
    """Fetch the primary image URL for a Met object."""
    try:
        r = await client.get(f"{MET_BASE}/objects/{object_id}")
        r.raise_for_status()
        data = r.json()

        # Only public domain objects have downloadable images
        if not data.get("isPublicDomain"):
            return None

        return data.get("primaryImage") or None
    except Exception:
        return None


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