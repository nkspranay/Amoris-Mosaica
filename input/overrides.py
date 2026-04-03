"""
Prompt override map — loaded from .env, never hardcoded.

When a user types one of the configured prompts (case-insensitive),
we skip the Unsplash/Pixabay fetch and serve a local asset instead.

Configure in .env like this:
    OVERRIDE_MAP=most beautiful flag:indian_flag.jpg;most beautiful country:india.jpg;pinnacle of beauty:her_1.jpg|her_2.jpg|her_3.jpg;g.o.a.t:ronaldo_1.jpg|ronaldo_2.jpg;greatest of all time:ronaldo_1.jpg|ronaldo_2.jpg

Format:
    prompt:file1.jpg|file2.jpg;prompt2:file1.jpg

Separators:
    ;  between entries
    :  between prompt and files
    |  between multiple files for the same prompt

IMPORTANT: assets/overrides/ is gitignored — images never go public.
IMPORTANT: OVERRIDE_MAP in .env is gitignored — prompts never go public.
"""

import os
import random
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
OVERRIDES_DIR = PROJECT_ROOT / "assets" / "overrides"


def _load_override_map() -> dict[str, list[str]]:
    raw = os.getenv("OVERRIDE_MAP", "").strip()
    if not raw:
        return {}

    result: dict[str, list[str]] = {}
    for entry in raw.split(";"):
        entry = entry.strip()
        if ":" not in entry:
            continue
        prompt, files_raw = entry.split(":", 1)
        prompt = prompt.strip().lower()
        files  = [f.strip() for f in files_raw.split("|") if f.strip()]
        if prompt and files:
            result[prompt] = files

    return result


_OVERRIDE_MAP: dict[str, list[str]] = _load_override_map()


def get_override(prompt: str) -> Path | None:
    key       = prompt.strip().lower()
    filenames = _OVERRIDE_MAP.get(key)

    if filenames is None:
        return None

    candidates = filenames.copy()
    random.shuffle(candidates)

    for filename in candidates:
        asset_path = OVERRIDES_DIR / filename
        if asset_path.exists():
            return asset_path

        stem = Path(filename).stem
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
            alt_path = OVERRIDES_DIR / f"{stem}{ext}"
            if alt_path.exists():
                return alt_path

    print(
        f"[overrides] Warning: override matched '{key}' "
        f"but no asset files found in {OVERRIDES_DIR}. "
        f"Falling back to API fetch."
    )
    return None


def list_overrides() -> list[str]:
    return list(_OVERRIDE_MAP.keys())