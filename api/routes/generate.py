import uuid
import asyncio
from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import Response, JSONResponse

from config import settings
from validators import (
    validate_target_image,
    validate_quality,
    validate_dataset_id,
)
from input.resolver import resolve_input, cleanup_temp
from engine.mosaic import generate_mosaic, MosaicRequest
from api.ws import build_emitter
from api.jobs import (
    create_job, get_job, update_job, result_path_for,
    JobStatus
)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /api/generate
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate_from_image(
    file:       UploadFile = File(...),
    dataset_id: str        = Form(...),
    quality:    int        = Form(default=2),
    session_id: str        = Form(default=""),
):
    _check(validate_quality(quality))
    _check(validate_dataset_id(dataset_id))

    file_bytes = await file.read()
    _check(validate_target_image(len(file_bytes), file.filename or "upload.jpg"))

    upload_path = _save_upload(file_bytes, file.filename or "upload.jpg")
    sid = session_id or str(uuid.uuid4())

    job = create_job()

    asyncio.create_task(
        _run_pipeline_async(
            image_path=upload_path,
            prompt=None,
            dataset_id=dataset_id,
            quality=quality,
            session_id=sid,
            job_id=job.job_id,
            cleanup_upload=True,
        )
    )

    return JSONResponse({
        "job_id":     job.job_id,
        "session_id": sid,
        "status":     JobStatus.PENDING,
    })


# ---------------------------------------------------------------------------
# POST /api/generate-from-text
# ---------------------------------------------------------------------------

@router.post("/generate-from-text")
async def generate_from_text(
    prompt:     str = Form(...),
    dataset_id: str = Form(...),
    quality:    int = Form(default=2),
    session_id: str = Form(default=""),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    _check(validate_quality(quality))
    _check(validate_dataset_id(dataset_id))

    sid = session_id or str(uuid.uuid4())
    job = create_job()

    asyncio.create_task(
        _run_pipeline_async(
            image_path=None,
            prompt=prompt.strip(),
            dataset_id=dataset_id,
            quality=quality,
            session_id=sid,
            job_id=job.job_id,
            cleanup_upload=False,
        )
    )

    return JSONResponse({
        "job_id":     job.job_id,
        "session_id": sid,
        "status":     JobStatus.PENDING,
    })


# ---------------------------------------------------------------------------
# GET /api/status/{job_id}
# ---------------------------------------------------------------------------

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "job_id":        job.job_id,
        "status":        job.status,
        "error":         job.error,
        "tile_count":    job.tile_count,
        "processing_ms": job.processing_ms,
        "grid_width":    job.grid_width,
        "grid_height":   job.grid_height,
    }


# ---------------------------------------------------------------------------
# GET /api/result/{job_id}
# ---------------------------------------------------------------------------

@router.get("/result/{job_id}")
async def get_result(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    if job.status == JobStatus.FAILED:
        raise HTTPException(status_code=500, detail=job.error or "Generation failed.")

    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=202, detail="Job still processing.")

    if not job.result_path or not job.result_path.exists():
        raise HTTPException(status_code=404, detail="Result file not found.")

    png_bytes = job.result_path.read_bytes()

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "X-Tile-Count":     str(job.tile_count),
            "X-Processing-Ms":  str(job.processing_ms),
            "X-Grid-Width":     str(job.grid_width),
            "X-Grid-Height":    str(job.grid_height),
            "X-Job-Id":         job_id,
            "Content-Disposition": "attachment; filename=mosaic.png",
        },
    )


# ---------------------------------------------------------------------------
# ACTUAL ASYNC PIPELINE
# ---------------------------------------------------------------------------

async def _run_pipeline_async(
    image_path:     Path | None,
    prompt:         str  | None,
    dataset_id:     str,
    quality:        int,
    session_id:     str,
    job_id:         str,
    cleanup_upload: bool,
) -> None:

    update_job(job_id, status=JobStatus.PROCESSING)
    emit = build_emitter(session_id)
    resolved = None

    try:
        resolved = await resolve_input(
            uploaded_path=image_path,
            prompt=prompt,
        )

        request = MosaicRequest(
            target_image_path=resolved.image_path,
            dataset_id=dataset_id,
            quality=quality,
            session_id=session_id,
        )

        result = await generate_mosaic(request, emit=emit)

        out_path = result_path_for(job_id)
        buffer = BytesIO()

        image = result.output_image
        if image.mode != "RGB":
            image = image.convert("RGB")

        image.save(
            buffer,
            format="PNG",
            optimize=True,
            compress_level=9
        )

        buffer.seek(0)
        out_path.write_bytes(buffer.getvalue())

        update_job(
            job_id,
            status=JobStatus.DONE,
            result_path=out_path,
            tile_count=result.tile_count,
            processing_ms=result.processing_ms,
            grid_width=result.grid_width,
            grid_height=result.grid_height,
        )

        try:
            await emit("done", 100, None)
        except:
            pass

    except Exception as e:
        print(f"[generate] Job {job_id} failed: {e}")
        update_job(job_id, status=JobStatus.FAILED, error=str(e))

        try:
            await emit("error", 0, None)
        except:
            pass

    finally:
        if resolved:
            cleanup_temp(resolved)
        if cleanup_upload and image_path and image_path.exists():
            image_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_upload(file_bytes: bytes, original_filename: str) -> Path:
    suffix    = Path(original_filename).suffix.lower() or ".jpg"
    temp_path = settings.temp_dir / f"upload_{uuid.uuid4().hex}{suffix}"
    temp_path.write_bytes(file_bytes)
    return temp_path


def _check(result) -> None:
    if not result.valid:
        raise HTTPException(status_code=400, detail=result.error)