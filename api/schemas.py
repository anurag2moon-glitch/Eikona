"""
api/schemas.py

Pydantic models for API requests and responses.
Designed to be frontend-friendly with clear field names & descriptions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    """Lifecycle states of an inference job."""
    queued     = "queued"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class JobCreatedResponse(BaseModel):
    """Returned when a new inference job is submitted."""
    job_id: str       = Field(..., description="Unique job identifier (UUID4).")
    status: JobStatus = Field(default=JobStatus.queued, description="Current job status.")
    message: str      = Field(default="Job submitted successfully.")


class JobStatusResponse(BaseModel):
    """Returned when polling for job status."""
    job_id: str                  = Field(..., description="Unique job identifier.")
    status: JobStatus            = Field(..., description="Current job status.")
    created_at: datetime         = Field(..., description="When the job was created.")
    started_at: Optional[datetime]   = Field(None, description="When processing began.")
    completed_at: Optional[datetime] = Field(None, description="When processing finished.")
    error: Optional[str]         = Field(None, description="Error message if failed.")
    result_url: Optional[str]    = Field(None, description="URL to download the result image.")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str            = Field("ok")
    version: str           = Field("0.1.0")
    checkpoint: str        = Field(..., description="Currently loaded checkpoint path.")
    device: str            = Field(..., description="Compute device (cpu/cuda/mps).")
    queue_depth: int       = Field(..., description="Number of jobs waiting in the queue.")


class CheckpointReloadResponse(BaseModel):
    """Returned after reloading a checkpoint."""
    message: str           = Field(...)
    checkpoint: str        = Field(...)


class QueueInfoResponse(BaseModel):
    """Queue statistics."""
    pending: int   = Field(..., description="Jobs waiting to be processed.")
    processing: int = Field(..., description="Jobs currently being processed.")
    completed: int = Field(..., description="Total completed jobs.")
    failed: int    = Field(..., description="Total failed jobs.")


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str = Field(..., description="Error description.")
