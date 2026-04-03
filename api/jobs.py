"""
In-memory job registry for async mosaic generation.

Jobs live in memory — no database needed.
Completed results are saved to temp/{job_id}.png on disk.
On Render free tier, temp files are ephemeral but that's fine for a demo.
"""

import uuid
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import settings


class JobStatus(str, Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    FAILED     = "failed"


@dataclass
class Job:
    job_id:      str
    status:      JobStatus  = JobStatus.PENDING
    error:       Optional[str] = None
    result_path: Optional[Path] = None   # path to saved PNG

    # Metadata returned to frontend on completion
    tile_count:    int = 0
    processing_ms: int = 0
    grid_width:    int = 0
    grid_height:   int = 0


# ---------------------------------------------------------------------------
# Registry — simple in-memory dict
# ---------------------------------------------------------------------------

_jobs: dict[str, Job] = {}


def create_job() -> Job:
    job = Job(job_id=str(uuid.uuid4()))
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)


def result_path_for(job_id: str) -> Path:
    """Returns the expected path for a job's result PNG."""
    return settings.temp_dir / f"result_{job_id}.png"


def cleanup_job(job_id: str) -> None:
    """Remove job from registry and delete result file."""
    job = _jobs.pop(job_id, None)
    if job and job.result_path and job.result_path.exists():
        job.result_path.unlink(missing_ok=True)