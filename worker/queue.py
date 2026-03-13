"""
worker/queue.py

File-system-based job queue.

Each job lives in JOBS_DIR/<job_id>/ with a meta.json file.
The queue manager scans for jobs with status == "queued", sorted by creation time,
and yields them one at a time (FIFO, single-consumer).

Why file-based?
  - Zero external dependencies (no Redis/RabbitMQ to install).
  - Jobs survive restarts — just restart the worker and it picks up where it left off.
  - Easy to inspect/debug: just cat the meta.json files.
  - Scalable path: swap this module with a Redis-backed implementation later.
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional

from api import config


class JobQueue:
    """
    Scans the jobs directory for pending work.
    NOT thread-safe by design — exactly one consumer should use this.
    """

    def __init__(self, jobs_dir: Optional[str] = None):
        self.jobs_dir = jobs_dir or config.JOBS_DIR
        os.makedirs(self.jobs_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def _meta_path(self, job_id: str) -> str:
        return os.path.join(self.jobs_dir, job_id, "meta.json")

    def _read_meta(self, job_id: str) -> dict:
        with open(self._meta_path(job_id)) as f:
            return json.load(f)

    def _write_meta(self, job_id: str, meta: dict):
        with open(self._meta_path(job_id), "w") as f:
            json.dump(meta, f, indent=2, default=str)

    # ------------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------------

    def next_job(self) -> Optional[dict]:
        """
        Return the oldest job with status == "queued", or None.
        Does NOT change the status — caller must call mark_processing().
        """
        if not os.path.exists(self.jobs_dir):
            return None

        candidates = []
        for entry in os.listdir(self.jobs_dir):
            meta_path = os.path.join(self.jobs_dir, entry, "meta.json")
            if not os.path.isfile(meta_path):
                continue
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                if meta.get("status") == "queued":
                    candidates.append(meta)
            except Exception:
                continue

        if not candidates:
            return None

        # Sort by creation time (FIFO)
        candidates.sort(key=lambda m: m.get("created_at", ""))
        return candidates[0]

    def mark_processing(self, job_id: str):
        meta = self._read_meta(job_id)
        meta["status"] = "processing"
        meta["started_at"] = datetime.now(timezone.utc).isoformat()
        self._write_meta(job_id, meta)

    def mark_completed(self, job_id: str, result_file: str):
        meta = self._read_meta(job_id)
        meta["status"] = "completed"
        meta["completed_at"] = datetime.now(timezone.utc).isoformat()
        meta["result_file"] = result_file
        self._write_meta(job_id, meta)

    def mark_failed(self, job_id: str, error: str):
        meta = self._read_meta(job_id)
        meta["status"] = "failed"
        meta["completed_at"] = datetime.now(timezone.utc).isoformat()
        meta["error"] = error
        self._write_meta(job_id, meta)

    # ------------------------------------------------------------------
    # Sentinel: checkpoint reload
    # ------------------------------------------------------------------

    def check_reload_sentinel(self) -> Optional[str]:
        """Check if the API requested a checkpoint reload. Returns path or None."""
        sentinel = os.path.join(self.jobs_dir, ".reload")
        if os.path.isfile(sentinel):
            with open(sentinel) as f:
                path = f.read().strip()
            os.remove(sentinel)
            return path
        return None
