"""
Input validation helpers.

Used by API route handlers to validate uploaded files before
they touch the engine. All validation logic lives here — routes stay clean.
"""

import zipfile
from pathlib import Path
from dataclasses import dataclass

from config import settings

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid:    bool
    error:    str | None = None    # Set if valid=False
    warning:  str | None = None    # Set for non-fatal issues (e.g. low tile count)


# ---------------------------------------------------------------------------
# Target image validation
# ---------------------------------------------------------------------------

def validate_target_image(file_size: int, filename: str) -> ValidationResult:
    """
    Validate a user-uploaded target image before saving to disk.
    Checks file size and extension.
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return ValidationResult(
            valid=False,
            error=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    max_bytes = settings.max_target_image_mb * 1024 * 1024
    if file_size > max_bytes:
        return ValidationResult(
            valid=False,
            error=f"File too large ({file_size // (1024*1024)}MB). Maximum is {settings.max_target_image_mb}MB.",
        )

    return ValidationResult(valid=True)


# ---------------------------------------------------------------------------
# Custom tile validation
# ---------------------------------------------------------------------------

def validate_tile_files(filenames: list[str]) -> ValidationResult:
    """
    Validate a list of individually uploaded tile filenames.
    Checks count limits and that all files are supported image types.
    """
    # Filter to supported images only
    valid_files = [f for f in filenames if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS]
    invalid_files = [f for f in filenames if Path(f).suffix.lower() not in SUPPORTED_EXTENSIONS]

    if invalid_files:
        print(f"[validators] Skipping {len(invalid_files)} unsupported files: {invalid_files[:5]}")

    count = len(valid_files)

    if count < settings.min_custom_tiles:
        return ValidationResult(
            valid=False,
            error=(
                f"Too few tiles ({count}). "
                f"Minimum is {settings.min_custom_tiles} images for a usable mosaic."
            ),
        )

    if count > settings.max_custom_tiles:
        return ValidationResult(
            valid=False,
            error=(
                f"Too many tiles ({count}). "
                f"Maximum is {settings.max_custom_tiles} images."
            ),
        )

    warning = None
    if count < settings.warn_custom_tiles:
        warning = (
            f"Only {count} tiles provided. "
            f"For best results, we recommend at least {settings.warn_custom_tiles} images. "
            f"Your mosaic may show visible repetition."
        )

    return ValidationResult(valid=True, warning=warning)


def validate_zip_file(file_size: int, filename: str) -> ValidationResult:
    """
    Validate a ZIP file upload before extracting.
    Checks size and that the filename ends in .zip.
    """
    if not filename.lower().endswith(".zip"):
        return ValidationResult(
            valid=False,
            error="Only .zip files are accepted for bulk tile uploads.",
        )

    max_bytes = settings.max_zip_mb * 1024 * 1024
    if file_size > max_bytes:
        return ValidationResult(
            valid=False,
            error=(
                f"ZIP too large ({file_size // (1024*1024)}MB). "
                f"Maximum is {settings.max_zip_mb}MB."
            ),
        )

    return ValidationResult(valid=True)


def validate_zip_contents(zip_path: Path) -> ValidationResult:
    """
    Open and inspect a ZIP file's contents.
    Counts valid image files inside and applies the same count rules
    as validate_tile_files.
    Also guards against zip bombs by checking uncompressed size.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            all_names = zf.namelist()

            # Zip bomb guard — reject if uncompressed size is suspiciously large
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > 2 * 1024 * 1024 * 1024:  # 2GB uncompressed
                return ValidationResult(
                    valid=False,
                    error="ZIP contents exceed 2GB uncompressed. Please split into smaller batches.",
                )

            # Count valid image files (ignore __MACOSX, hidden files, directories)
            valid_images = [
                name for name in all_names
                if not name.startswith("__")
                and not name.startswith(".")
                and not name.endswith("/")
                and Path(name).suffix.lower() in SUPPORTED_EXTENSIONS
            ]

    except zipfile.BadZipFile:
        return ValidationResult(
            valid=False,
            error="Invalid or corrupted ZIP file.",
        )

    return validate_tile_files(valid_images)


# ---------------------------------------------------------------------------
# Quality level validation
# ---------------------------------------------------------------------------

def validate_quality(quality: int) -> ValidationResult:
    """Validate the quality level parameter."""
    if quality not in {1, 2, 3}:
        return ValidationResult(
            valid=False,
            error=f"Invalid quality level '{quality}'. Must be 1 (low), 2 (medium), or 3 (high).",
        )
    return ValidationResult(valid=True)


# ---------------------------------------------------------------------------
# Dataset ID validation
# ---------------------------------------------------------------------------

def validate_dataset_id(dataset_id: str) -> ValidationResult:
    """Validate the dataset_id parameter."""
    valid_ids = {"nature", "artworks", "space", "custom"}
    if dataset_id not in valid_ids:
        return ValidationResult(
            valid=False,
            error=f"Invalid dataset_id '{dataset_id}'. Must be one of: {', '.join(sorted(valid_ids))}.",
        )
    return ValidationResult(valid=True)