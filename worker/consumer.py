"""
worker/consumer.py

The inference worker — runs in its own process, picks up one job at a time
from the file-based queue, runs the InferenceEngine, saves the result.

Key properties:
  - Single-threaded: one job at a time (GPU safety).
  - Loads the model once, reuses across jobs.
  - Supports hot-reload of checkpoints via sentinel file.
  - Graceful shutdown on SIGINT / SIGTERM.
"""

import os
import sys
import time
import signal
import traceback

from PIL import Image

from api import config
from worker.queue import JobQueue
from eikona.inference_engine import InferenceEngine


class Worker:
    """Inference worker that polls the job queue and processes one job at a time."""

    def __init__(self):
        self.queue = JobQueue()
        self.engine: InferenceEngine | None = None
        self._running = True
        self._current_checkpoint = config.CHECKPOINT_PATH

        # Graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        print(f"\n[Worker] Received signal {signum}, shutting down gracefully...")
        self._running = False

    def _ensure_engine(self):
        """Lazy-load the inference engine on first job (or after reload)."""
        if self.engine is None:
            print(f"[Worker] Loading model from: {self._current_checkpoint}")
            print(f"[Worker] Index directory:    {config.INDEX_DIR}")
            self.engine = InferenceEngine(
                checkpoint_path=self._current_checkpoint,
                index_dir=config.INDEX_DIR,
            )
            print(f"[Worker] Model loaded on device: {self.engine.device}")

    def _check_reload(self):
        """Check if the API asked us to reload a checkpoint."""
        new_ckpt = self.queue.check_reload_sentinel()
        if new_ckpt and new_ckpt != self._current_checkpoint:
            print(f"[Worker] Reloading checkpoint: {new_ckpt}")
            if self.engine is not None:
                self.engine.reload_checkpoint(new_ckpt)
            self._current_checkpoint = new_ckpt
            print(f"[Worker] Checkpoint reloaded successfully.")

    def _process_job(self, meta: dict):
        """Run inference for a single job."""
        job_id = meta["job_id"]
        input_file = meta["input_file"]
        checkpoint = meta.get("checkpoint", self._current_checkpoint)

        print(f"[Worker] Processing job {job_id}")
        self.queue.mark_processing(job_id)

        try:
            # Handle per-job checkpoint override
            if checkpoint != self._current_checkpoint:
                print(f"[Worker] Job requests checkpoint: {checkpoint}")
                self.engine.reload_checkpoint(checkpoint)
                self._current_checkpoint = checkpoint

            # Open input image
            input_image = Image.open(input_file).convert("RGB")

            # Run inference
            result_image = self.engine.run(input_image)

            # Save result
            job_dir = os.path.join(config.JOBS_DIR, job_id)
            result_path = os.path.join(job_dir, "result.png")
            result_image.save(result_path)

            self.queue.mark_completed(job_id, result_path)
            print(f"[Worker] Job {job_id} completed → {result_path}")

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[Worker] Job {job_id} FAILED: {e}\n{tb}")
            self.queue.mark_failed(job_id, str(e))

    def _check_auto_update(self):
        """Check if a newer checkpoint has appeared in the filesystem."""
        latest = config.get_latest_checkpoint()
        if latest and latest != self._current_checkpoint:
            print(f"[Worker] Found newer checkpoint: {latest}")
            if self.engine is not None:
                self.engine.reload_checkpoint(latest)
            self._current_checkpoint = latest
            print(f"[Worker] Auto-updated to latest weights.")

    def run(self):
        """Main loop — poll queue, process one job at a time."""
        print("=" * 60)
        print("  Eikona Worker")
        print(f"  Checkpoint : {self._current_checkpoint}")
        print(f"  Index dir  : {config.INDEX_DIR}")
        print(f"  Jobs dir   : {config.JOBS_DIR}")
        print(f"  Poll interval: {config.WORKER_POLL_INTERVAL}s")
        print("=" * 60)

        # Discard existing queued jobs on startup (User Request)
        print("[Worker] Cleaning up old pending jobs...")
        while True:
            job = self.queue.next_job()
            if job is None:
                break
            print(f"   - Discarding stale job: {job['job_id']}")
            self.queue.mark_failed(job['job_id'], "Worker was offline; job discarded on restart.")
        print("[Worker] Cleanup complete. Ready for new jobs.")

        while self._running:
            # Check for checkpoint reload requests (Sentinel)
            self._check_reload()
            
            # Check for newer checkpoints automatically
            self._check_auto_update()

            # Pick up next job
            job = self.queue.next_job()

            if job is None:
                time.sleep(config.WORKER_POLL_INTERVAL)
                continue

            # Lazy-load engine on first job
            self._ensure_engine()
            self._process_job(job)

        print("[Worker] Stopped.")


def main():
    """Entry point for the worker process."""
    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
