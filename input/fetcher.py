"""
Text-to-image fetcher.

Given a text prompt, fetches the most relevant image from:
  1. Unsplash (primary — higher quality)
  2. Pixabay  (fallback — broader coverage, better for people/landmarks)

Returns a Path to a temp file containing the downloaded image.
The caller is responsible for cleaning up the temp file after use.
"""

import os
import httpx
import tempfile
from pathlib import Path
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
PIXABAY_API_KEY     = os.getenv("PIXABAY_API_KEY", "")

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
PIXABAY_SEARCH_URL  = "https://pixabay.com/api/"

# Use "regular" size from Unsplash — good quality (~1080px) without being huge
UNSPLASH_IMAGE_SIZE = "regular"

REQUEST_TIMEOUT = 20  # seconds


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_image_for_prompt(prompt: str) -> Path:
    """
    Fetch the best matching image for a text prompt.

    Tries Unsplash first. Falls back to Pixabay if Unsplash returns no results
    or if the API key is not configured.

    Returns a Path to a downloaded temp file (JPEG).
    Raises RuntimeError if both sources fail.
    """
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:

        # --- Try Unsplash first ---
        if UNSPLASH_ACCESS_KEY:
            result = await _fetch_from_unsplash(client, prompt)
            if result:
                return result
            print(f"[fetcher] Unsplash returned no results for '{prompt}' — trying Pixabay")
        else:
            print("[fetcher] UNSPLASH_ACCESS_KEY not set — skipping Unsplash")

        # --- Fall back to Pixabay ---
        if PIXABAY_API_KEY:
            result = await _fetch_from_pixabay(client, prompt)
            if result:
                return result
            print(f"[fetcher] Pixabay returned no results for '{prompt}'")
        else:
            print("[fetcher] PIXABAY_API_KEY not set — skipping Pixabay")

    raise RuntimeError(
        f"Could not find an image for prompt '{prompt}'. "
        f"Try a different search term."
    )


# ---------------------------------------------------------------------------
# Unsplash
# ---------------------------------------------------------------------------

async def _fetch_from_unsplash(
    client: httpx.AsyncClient,
    prompt: str,
) -> Path | None:
    """Search Unsplash and download the top result."""
    try:
        response = await client.get(
            UNSPLASH_SEARCH_URL,
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            params={
                "query":    prompt,
                "per_page": 1,
                "order_by": "relevant",
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])

        if not results:
            return None

        image_url = results[0].get("urls", {}).get(UNSPLASH_IMAGE_SIZE)
        if not image_url:
            return None

        return await _download_to_temp(client, image_url, source="unsplash")

    except httpx.HTTPStatusError as e:
        print(f"[fetcher] Unsplash HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"[fetcher] Unsplash error: {e}")
        return None


# ---------------------------------------------------------------------------
# Pixabay
# ---------------------------------------------------------------------------

async def _fetch_from_pixabay(
    client: httpx.AsyncClient,
    prompt: str,
) -> Path | None:
    """Search Pixabay and download the top result."""
    try:
        response = await client.get(
            PIXABAY_SEARCH_URL,
            params={
                "key":         PIXABAY_API_KEY,
                "q":           prompt,
                "image_type":  "photo",
                "per_page":    3,
                "safesearch":  "true",
                "order":       "popular",
            },
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])

        if not hits:
            return None

        # Pixabay's "webformatURL" is medium quality — good enough for target image
        image_url = hits[0].get("webformatURL")
        if not image_url:
            return None

        return await _download_to_temp(client, image_url, source="pixabay")

    except httpx.HTTPStatusError as e:
        print(f"[fetcher] Pixabay HTTP error: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"[fetcher] Pixabay error: {e}")
        return None


# ---------------------------------------------------------------------------
# Shared download helper
# ---------------------------------------------------------------------------

async def _download_to_temp(
    client: httpx.AsyncClient,
    url: str,
    source: str,
) -> Path | None:
    """
    Download an image URL to a named temp file and return its Path.
    Validates it's a real image before returning.
    The file is NOT auto-deleted — caller must clean up after use.
    """
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()

        # Validate it's a real image
        img = Image.open(BytesIO(response.content)).convert("RGB")

        # Save to a named temp file so the pipeline can read it by path
        suffix = ".jpg"
        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            prefix=f"mosaic_{source}_",
        )
        img.save(tmp.name, "JPEG", quality=95)
        tmp.close()

        print(f"[fetcher] Downloaded from {source}: {Path(tmp.name).name}")
        return Path(tmp.name)

    except Exception as e:
        print(f"[fetcher] Download failed from {source} ({url[:60]}...): {e}")
        return None