"""
api/main.py

FastAPI application — the public-facing API layer.

Routes:
    POST   /api/v1/generate         — Submit a new inference job (image upload).
    GET    /api/v1/jobs/{job_id}    — Poll job status.
    GET    /api/v1/jobs/{job_id}/result  — Download the result image.
    GET    /api/v1/queue            — Queue statistics.
    POST   /api/v1/reload           — Hot-reload a checkpoint.
    GET    /health                  — Health check.
"""

import os
import uuid
import json
import shutil
from datetime import datetime, timezone

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api import config
from api.schemas import (
    JobCreatedResponse,
    JobStatusResponse,
    JobStatus,
    HealthResponse,
    CheckpointReloadResponse,
    QueueInfoResponse,
    ErrorResponse,
)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Eikona API",
    description=(
        "RAG-Guided Pix2Pix image-to-image translation API.\n\n"
        "Upload a sketch / edge-map and receive a photorealistic translation "
        "using retrieval-augmented generation."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    responses={
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)

# CORS — allow any origin so frontends can call freely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jobs_dir() -> str:
    os.makedirs(config.JOBS_DIR, exist_ok=True)
    return config.JOBS_DIR


def _job_dir(job_id: str) -> str:
    return os.path.join(_jobs_dir(), job_id)


def _read_meta(job_id: str) -> dict:
    meta_path = os.path.join(_job_dir(job_id), "meta.json")
    if not os.path.exists(meta_path):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    with open(meta_path) as f:
        return json.load(f)


def _write_meta(job_id: str, meta: dict):
    meta_path = os.path.join(_job_dir(job_id), "meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)


def _count_jobs_by_status(status: str) -> int:
    jobs = _jobs_dir()
    count = 0
    if not os.path.exists(jobs):
        return 0
    for jid in os.listdir(jobs):
        meta_path = os.path.join(jobs, jid, "meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path) as f:
                    m = json.load(f)
                if m.get("status") == status:
                    count += 1
            except Exception:
                pass
    return count


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
)
async def health():
    """Returns API health, loaded checkpoint, and queue depth."""
    return HealthResponse(
        status="ok",
        version="0.1.0",
        checkpoint=config.CHECKPOINT_PATH,
        device="auto",
        queue_depth=_count_jobs_by_status("queued"),
    )


@app.post(
    "/api/v1/generate",
    response_model=JobCreatedResponse,
    status_code=202,
    tags=["Inference"],
    summary="Submit an inference job",
    responses={
        202: {"description": "Job accepted and queued."},
        400: {"model": ErrorResponse, "description": "Invalid image upload."},
    },
)
async def generate(
    image: UploadFile = File(..., description="Input sketch / edge-map image (JPEG or PNG)."),
    checkpoint: str = Query(
        default=None,
        description="Optional: override checkpoint path for this job.",
    ),
):
    """
    Upload an image to start an inference job.

    The job is placed in a queue and processed by the worker.
    Use the returned `job_id` to poll for status via `GET /api/v1/jobs/{job_id}`.
    """
    # Validate content type
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {image.content_type}. Use JPEG, PNG, or WebP.",
        )

    job_id = str(uuid.uuid4())
    job_path = _job_dir(job_id)
    os.makedirs(job_path, exist_ok=True)

    # Save uploaded image
    ext = image.filename.split(".")[-1] if image.filename else "png"
    input_filename = f"input.{ext}"
    input_path = os.path.join(job_path, input_filename)
    with open(input_path, "wb") as f:
        shutil.copyfileobj(image.file, f)

    # Write job metadata
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "job_id": job_id,
        "status": JobStatus.queued.value,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "input_file": input_path,
        "result_file": None,
        "checkpoint": checkpoint or config.CHECKPOINT_PATH,
    }
    _write_meta(job_id, meta)

    return JobCreatedResponse(job_id=job_id, status=JobStatus.queued)


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["Jobs"],
    summary="Get job status",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found."},
    },
)
async def get_job_status(job_id: str):
    """
    Poll the status of a previously submitted job.

    Statuses: `queued` → `processing` → `completed` | `failed`.
    When `completed`, the `result_url` field will contain the download path.
    """
    meta = _read_meta(job_id)
    result_url = None
    if meta.get("result_file") and os.path.isfile(meta["result_file"]):
        result_url = f"/api/v1/jobs/{job_id}/result"
    return JobStatusResponse(
        job_id=meta["job_id"],
        status=meta["status"],
        created_at=meta["created_at"],
        started_at=meta.get("started_at"),
        completed_at=meta.get("completed_at"),
        error=meta.get("error"),
        result_url=result_url,
    )


@app.get(
    "/api/v1/jobs/{job_id}/result",
    tags=["Jobs"],
    summary="Download result image",
    responses={
        200: {"content": {"image/png": {}}, "description": "Result image."},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Job not yet completed."},
    },
)
async def get_job_result(job_id: str):
    """Download the generated result image for a completed job."""
    meta = _read_meta(job_id)
    if meta["status"] != JobStatus.completed.value:
        raise HTTPException(status_code=409, detail=f"Job status is '{meta['status']}', not completed.")
    result_file = meta.get("result_file")
    if not result_file or not os.path.isfile(result_file):
        raise HTTPException(status_code=404, detail="Result file not found on disk.")
    return FileResponse(result_file, media_type="image/png", filename=f"{job_id}_result.png")


@app.get(
    "/api/v1/queue",
    response_model=QueueInfoResponse,
    tags=["System"],
    summary="Queue statistics",
)
async def queue_info():
    """Returns a breakdown of jobs by status."""
    return QueueInfoResponse(
        pending=_count_jobs_by_status("queued"),
        processing=_count_jobs_by_status("processing"),
        completed=_count_jobs_by_status("completed"),
        failed=_count_jobs_by_status("failed"),
    )


@app.post(
    "/api/v1/reload",
    response_model=CheckpointReloadResponse,
    tags=["System"],
    summary="Hot-reload checkpoint",
)
async def reload_checkpoint(
    checkpoint: str = Query(..., description="Absolute or relative path to the .pth checkpoint."),
):
    """
    Tell the worker to load a different checkpoint.

    This writes a sentinel file that the worker picks up on its next iteration.
    The change takes effect on the *next* processed job.
    """
    if not os.path.isfile(checkpoint):
        raise HTTPException(status_code=404, detail=f"Checkpoint file not found: {checkpoint}")
    # Write a reload sentinel for the worker
    sentinel_path = os.path.join(config.JOBS_DIR, ".reload")
    os.makedirs(config.JOBS_DIR, exist_ok=True)
    with open(sentinel_path, "w") as f:
        f.write(checkpoint)
    config.CHECKPOINT_PATH = checkpoint
    return CheckpointReloadResponse(message="Checkpoint reload scheduled.", checkpoint=checkpoint)


@app.get(
    "/api/v1/checkpoints",
    tags=["System"],
    summary="List available checkpoints",
)
async def list_checkpoints():
    """List all .pth files in the checkpoints directory."""
    ckpt_dir = os.path.join(config.PROJECT_ROOT, "checkpoints")
    if not os.path.isdir(ckpt_dir):
        return {"checkpoints": []}
    files = sorted([
        f for f in os.listdir(ckpt_dir) if f.endswith(".pth")
    ])
    return {
        "checkpoints": [
            {
                "name": f,
                "path": os.path.join(ckpt_dir, f),
                "size_mb": round(os.path.getsize(os.path.join(ckpt_dir, f)) / (1024 * 1024), 1),
            }
            for f in files
        ]
    }
