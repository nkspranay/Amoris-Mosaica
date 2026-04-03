import time
import asyncio
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Awaitable, Optional
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from PIL import Image, ImageFilter

from engine.preprocessor import preprocess_image
from engine.splitter import split_into_grid
from engine.assembler import assemble_mosaic
from tiles.tile_utils import load_tile_index, load_tiles_for_indices
from tiles.color_match import ColorMatcher


# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

@dataclass
class MosaicRequest:
    target_image_path: Path
    dataset_id: str
    quality: int
    session_id: str
    custom_tiles_path: Optional[Path] = None


@dataclass
class MosaicResult:
    output_image: Image.Image
    tile_count: int
    processing_ms: int
    grid_width: int
    grid_height: int


# ---------------------------------------------------------------------------
# Dynamic cell size
# ---------------------------------------------------------------------------

def compute_cell_size(image_width, image_height, quality):
    if quality == 1:
        target_tiles = 15000
    elif quality == 2:
        target_tiles = 40000
    else:
        target_tiles = 75000

    aspect_ratio = image_width / image_height
    grid_height  = int(math.sqrt(target_tiles / aspect_ratio))
    grid_width   = int(target_tiles / grid_height)
    cell_size_w  = image_width  // grid_width
    cell_size_h  = image_height // grid_height
    return max(2, min(cell_size_w, cell_size_h))


# ---------------------------------------------------------------------------
# Face detection
# ---------------------------------------------------------------------------

def detect_face_region(image: Image.Image):
    img  = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
    )
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return (x, y, x + w, y + h)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def generate_mosaic(
    request: MosaicRequest,
    emit: Callable[[str, int, Optional[int]], Awaitable[None]],
) -> MosaicResult:

    start_time = time.monotonic()

    # --- Preprocess ---
    await emit("preprocess", 0, None)
    await asyncio.sleep(0)

    target_image = preprocess_image(request.target_image_path)
    face_box     = detect_face_region(target_image)

    await emit("preprocess", 15, None)
    await asyncio.sleep(0)

    # --- Load tile INDEX only (tiny memory, no images) ---
    await emit("load_tiles", 15, None)
    await asyncio.sleep(0)

    index   = load_tile_index(
        dataset_id=request.dataset_id,
        custom_path=request.custom_tiles_path,
    )
    matcher = ColorMatcher(index)

    await emit("load_tiles", 30, None)
    await asyncio.sleep(0)

    # --- Cell size ---
    cell_size = compute_cell_size(
        target_image.width,
        target_image.height,
        request.quality
    )

    # ============================================================
    # PASS 1 — BASE: match cells → collect indices
    # ============================================================
    await emit("split", 30, None)
    await asyncio.sleep(0)

    cell_patches, cell_avgs, grid_width, grid_height = split_into_grid(
        target_image, cell_size=cell_size
    )

    await emit("split", 40, None)
    await asyncio.sleep(0)

    await emit("match", 40, None)
    await asyncio.sleep(0)

    base_indices = await _match_cells(
        cell_patches, cell_avgs, matcher,
        face_box, cell_size, grid_width,
        prioritize_face=False, pass_name="Base"
    )

    await emit("match", 65, None)
    await asyncio.sleep(0)

    # ============================================================
    # PASS 2 — DETAIL: finer grid → collect indices
    # ============================================================
    detail_cell_size = max(6, cell_size // 2)

    detail_patches, detail_avgs, dw, dh = split_into_grid(
        target_image, cell_size=detail_cell_size
    )

    detail_indices = await _match_cells(
        detail_patches, detail_avgs, matcher,
        face_box, detail_cell_size, dw,
        prioritize_face=True, pass_name="Detail"
    )

    await emit("match", 85, None)
    await asyncio.sleep(0)

    # ============================================================
    # LOAD only the unique tiles actually used across both passes
    # ============================================================
    await emit("assemble", 85, None)
    await asyncio.sleep(0)

    all_used_indices = set(base_indices) | set(detail_indices)
    print(f"[mosaic] Loading {len(all_used_indices)} unique tiles for assembly "
          f"(from {index.count} total)")

    tile_images = load_tiles_for_indices(index, all_used_indices)

    # ============================================================
    # ASSEMBLE both passes
    # ============================================================
    base_mosaic = assemble_mosaic(
        base_indices, tile_images, grid_width, grid_height, cell_size
    )

    detail_mosaic = assemble_mosaic(
        detail_indices, tile_images, dw, dh, detail_cell_size
    )
    detail_mosaic = detail_mosaic.resize(base_mosaic.size)

    # ============================================================
    # COMBINE
    # ============================================================
    combined = Image.blend(base_mosaic, detail_mosaic, alpha=0.4)

    # ============================================================
    # FACE ENHANCEMENT
    # ============================================================
    if face_box:
        fx1, fy1, fx2, fy2 = face_box
        pad = 30
        fx1 = max(0, fx1 - pad)
        fy1 = max(0, fy1 - pad)
        fx2 = min(combined.width,  fx2 + pad)
        fy2 = min(combined.height, fy2 + pad)

        mask     = np.zeros((combined.height, combined.width), dtype=np.float32)
        cx       = (fx1 + fx2) // 2
        cy       = (fy1 + fy2) // 2
        max_dist = max(fx2 - fx1, fy2 - fy1) // 2

        for y in range(fy1, fy2):
            for x in range(fx1, fx2):
                dist      = ((x - cx)**2 + (y - cy)**2) ** 0.5
                mask[y, x] = 1.0 - min(1.0, dist / max_dist)

        mask_img      = Image.fromarray((mask * 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(radius=15)
        )
        strong_detail = Image.blend(base_mosaic, detail_mosaic, alpha=0.6)
        combined      = Image.composite(strong_detail, combined, mask_img)

    # ============================================================
    # FINAL BLEND WITH ORIGINAL
    # ============================================================
    original_resized = target_image.resize(combined.size)
    output_image     = Image.blend(combined, original_resized, alpha=0.25)

    await emit("assemble", 100, None)
    await asyncio.sleep(0)

    processing_ms = int((time.monotonic() - start_time) * 1000)

    return MosaicResult(
        output_image=output_image,
        tile_count=len(base_indices) + len(detail_indices),
        processing_ms=processing_ms,
        grid_width=grid_width,
        grid_height=grid_height,
    )


# ---------------------------------------------------------------------------
# Parallel matching — returns LIST OF INDICES, not images
# ---------------------------------------------------------------------------

async def _match_cells(
    cell_patches,
    cell_avgs,
    matcher: ColorMatcher,
    face_box,
    cell_size,
    grid_width,
    prioritize_face=False,
    pass_name="Matching"
) -> list[int]:

    total_cells = len(cell_patches)
    loop        = asyncio.get_running_loop()

    def process(i):
        patch = cell_patches[i]
        avg   = cell_avgs[i]

        col = i % grid_width
        row = i // grid_width
        x   = col * cell_size
        y   = row * cell_size

        if face_box and prioritize_face:
            fx1, fy1, fx2, fy2 = face_box
            _ = (fx1 <= x <= fx2) and (fy1 <= y <= fy2)

        return matcher.find_closest_index(patch, avg)

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        indices = await loop.run_in_executor(
            executor,
            lambda: list(map(process, range(total_cells)))
        )

    print(f"[{pass_name}] {total_cells} cells matched")
    return indices