"""
Tiles routes.

POST /api/upload-tiles         — individual image uploads
POST /api/upload-tiles/chunk   — chunked ZIP upload for large datasets
"""

import uuid
import shutil
import zipfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from config import settings
from validators import (
    validate_tile_files,
    validate_zip_file,
    validate_zip_contents,
)

router = APIRouter()

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TileUploadResponse(BaseModel):
    session_tile_id: str    # ID used to reference this dataset in /generate
    tile_count:      int
    quality_badge:   str    # "excellent" | "good" | "fair"
    warning:         str | None = None


class ChunkResponse(BaseModel):
    session_tile_id: str
    chunks_received: int
    total_chunks:    int
    complete:        bool
    tile_count:      int | None = None   # Only set when complete=True
    quality_badge:   str | None = None   # Only set when complete=True
    warning:         str | None = None


# ---------------------------------------------------------------------------
# POST /api/upload-tiles — individual images
# ---------------------------------------------------------------------------

@router.post("/upload-tiles", response_model=TileUploadResponse)
async def upload_individual_tiles(
    files:      list[UploadFile] = File(...),
    session_id: str              = Form(default=""),
):
    """
    Upload individual tile images.
    All files are saved to a session temp directory.
    Returns a session_tile_id to reference this dataset in /generate.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    # Validate file count and extensions
    filenames = [f.filename or "tile.jpg" for f in files]
    result = validate_tile_files(filenames)
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.error)

    # Create a session directory for this tile set
    session_tile_id = session_id or str(uuid.uuid4())
    tile_dir = settings.temp_dir / f"tiles_{session_tile_id}"
    tile_dir.mkdir(parents=True, exist_ok=True)

    # Save each valid image file
    saved = 0
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        dest = tile_dir / f"{uuid.uuid4().hex}{ext}"
        content = await upload.read()

        # Per-file size check
        if len(content) > settings.max_single_tile_mb * 1024 * 1024:
            continue  # Skip oversized tiles silently

        dest.write_bytes(content)
        saved += 1

    if saved < settings.min_custom_tiles:
        shutil.rmtree(tile_dir, ignore_errors=True)
        raise HTTPException(
            status_code=400,
            detail=f"Only {saved} valid images after filtering. Minimum is {settings.min_custom_tiles}.",
        )

    return TileUploadResponse(
        session_tile_id=session_tile_id,
        tile_count=saved,
        quality_badge=_quality_badge(saved),
        warning=result.warning,
    )


# ---------------------------------------------------------------------------
# POST /api/upload-tiles/chunk — chunked ZIP upload
# ---------------------------------------------------------------------------

@router.post("/upload-tiles/chunk", response_model=ChunkResponse)
async def upload_tile_chunk(
    chunk:        UploadFile = File(...),
    chunk_index:  int        = Form(...),
    total_chunks: int        = Form(...),
    session_id:   str        = Form(...),
    filename:     str        = Form(...),
):
    """
    Upload a ZIP file in chunks to handle large datasets and internet failures.
    Send chunks sequentially with chunk_index starting at 0.
    On the final chunk, the ZIP is assembled, validated, and extracted.
    Returns complete=True with tile metadata when all chunks are received.
    """
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted.")

    # Directory for this session's chunks
    chunk_dir = settings.temp_dir / f"chunks_{session_id}"
    chunk_dir.mkdir(parents=True, exist_ok=True)

    # Save this chunk
    chunk_path = chunk_dir / f"chunk_{chunk_index:05d}"
    chunk_content = await chunk.read()
    chunk_path.write_bytes(chunk_content)

    chunks_received = len(list(chunk_dir.glob("chunk_*")))
    is_complete = chunks_received >= total_chunks

    if not is_complete:
        return ChunkResponse(
            session_tile_id=session_id,
            chunks_received=chunks_received,
            total_chunks=total_chunks,
            complete=False,
        )

    # --- All chunks received — assemble the ZIP ---
    zip_path = settings.temp_dir / f"upload_{session_id}.zip"
    try:
        _assemble_chunks(chunk_dir, zip_path, total_chunks)
    except Exception as e:
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to assemble ZIP: {e}")

    # Validate ZIP size and contents
    zip_size = zip_path.stat().st_size
    size_result = validate_zip_file(zip_size, filename)
    if not size_result.valid:
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=size_result.error)

    contents_result = validate_zip_contents(zip_path)
    if not contents_result.valid:
        zip_path.unlink(missing_ok=True)
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=contents_result.error)

    # Extract ZIP to a session tile directory
    tile_dir = settings.temp_dir / f"tiles_{session_id}"
    tile_dir.mkdir(parents=True, exist_ok=True)
    tile_count = _extract_zip(zip_path, tile_dir)

    # Cleanup chunks and zip
    shutil.rmtree(chunk_dir, ignore_errors=True)
    zip_path.unlink(missing_ok=True)

    return ChunkResponse(
        session_tile_id=session_id,
        chunks_received=chunks_received,
        total_chunks=total_chunks,
        complete=True,
        tile_count=tile_count,
        quality_badge=_quality_badge(tile_count),
        warning=contents_result.warning,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assemble_chunks(chunk_dir: Path, output_path: Path, total_chunks: int) -> None:
    """Concatenate ordered chunk files into a single ZIP file."""
    with open(output_path, "wb") as outfile:
        for i in range(total_chunks):
            chunk_path = chunk_dir / f"chunk_{i:05d}"
            if not chunk_path.exists():
                raise FileNotFoundError(f"Missing chunk {i}")
            outfile.write(chunk_path.read_bytes())


def _extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """
    Extract valid image files from a ZIP into dest_dir.
    Returns count of successfully extracted images.
    Skips directories, hidden files, and non-image files.
    """
    extracted = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            name = member.filename

            # Skip directories, hidden files, macOS metadata
            if name.endswith("/") or name.startswith("__") or name.startswith("."):
                continue

            ext = Path(name).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            # Flatten directory structure — save all images to dest_dir directly
            flat_name = f"{uuid.uuid4().hex}{ext}"
            dest_path = dest_dir / flat_name

            with zf.open(member) as src, open(dest_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            extracted += 1

    return extracted


def _quality_badge(tile_count: int) -> str:
    if tile_count >= 500:
        return "excellent"
    if tile_count >= 200:
        return "good"
    return "fair"