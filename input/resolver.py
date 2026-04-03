"""
Input resolver.

Single entry point for all target image resolution.
Decides which path to take based on what the user provided:

  1. Direct upload  → validate and return the uploaded file path
  2. Text prompt    → check override map first, then fetch from API
  3. Override match → return local asset path directly, skip API entirely

Always returns a ResolvedInput containing:
  - image_path : Path to the target image (temp file or uploaded file)
  - is_temp    : Whether the file is a temp file that needs cleanup after use
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from input.overrides import get_override
from input.fetcher import fetch_image_for_prompt


# ---------------------------------------------------------------------------
# Data contract
# ---------------------------------------------------------------------------

@dataclass
class ResolvedInput:
    image_path: Path    # Path to the resolved target image
    is_temp:    bool    # True if this is a temp file that must be deleted after use


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def resolve_input(
    uploaded_path: Path | None = None,
    prompt:        str  | None = None,
) -> ResolvedInput:
    """
    Resolve the target image from either an uploaded file or a text prompt.

    Exactly one of uploaded_path or prompt must be provided.
    Raises ValueError if neither or both are provided.
    Raises RuntimeError if the prompt cannot be resolved to an image.
    """
    if uploaded_path and prompt:
        raise ValueError("Provide either an uploaded image or a text prompt, not both.")

    if not uploaded_path and not prompt:
        raise ValueError("Either uploaded_path or prompt must be provided.")

    if uploaded_path:
        return _resolve_upload(uploaded_path)

    return await _resolve_prompt(prompt.strip())


def cleanup_temp(resolved: ResolvedInput) -> None:
    """
    Delete the temp file if it was created during resolution.
    Call this after mosaic generation is complete.
    Safe to call even if the file has already been deleted.
    """
    if resolved.is_temp and resolved.image_path.exists():
        try:
            resolved.image_path.unlink()
        except Exception as e:
            print(f"[resolver] Warning: could not delete temp file {resolved.image_path}: {e}")


# ---------------------------------------------------------------------------
# Internal resolvers
# ---------------------------------------------------------------------------

def _resolve_upload(uploaded_path: Path) -> ResolvedInput:
    """
    Handle a direct file upload.
    The file already exists on disk — just validate and return.
    """
    if not uploaded_path.exists():
        raise FileNotFoundError(f"Uploaded file not found: {uploaded_path}")

    return ResolvedInput(
        image_path=uploaded_path,
        is_temp=False,   # Caller manages the uploaded file's lifecycle
    )


async def _resolve_prompt(prompt: str) -> ResolvedInput:
    """
    Handle a text prompt.

    Resolution order:
      1. Check override map — if matched, return local asset (not a temp file)
      2. Fetch from Unsplash → Pixabay — return temp file
    """
    # --- Step 1: Check override map ---
    override_path = get_override(prompt)
    if override_path:
        print(f"[resolver] Override matched: '{prompt}' → {override_path.name}")
        return ResolvedInput(
            image_path=override_path,
            is_temp=False,   # Local asset — never delete
        )

    # --- Step 2: Fetch from external API ---
    print(f"[resolver] No override for '{prompt}' — fetching from API")
    temp_path = await fetch_image_for_prompt(prompt)

    return ResolvedInput(
        image_path=temp_path,
        is_temp=True,   # Temp file — delete after mosaic generation
    )