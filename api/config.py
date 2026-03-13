"""
api/config.py

Centralised settings for the Eikona API, loaded from environment variables
with sensible defaults so it works out-of-the-box.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths  (relative to project root by default)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHECKPOINT_PATH: str = os.getenv(
    "EIKONA_CHECKPOINT",
    str(PROJECT_ROOT / "checkpoints" / "G_epoch1.pth"),
)

INDEX_DIR: str = os.getenv(
    "EIKONA_INDEX_DIR",
    str(PROJECT_ROOT / "index"),
)

OUTPUT_DIR: str = os.getenv(
    "EIKONA_OUTPUT_DIR",
    str(PROJECT_ROOT / "outputs"),
)

# ---------------------------------------------------------------------------
# Queue / Job storage
# ---------------------------------------------------------------------------

JOBS_DIR: str = os.getenv(
    "EIKONA_JOBS_DIR",
    str(PROJECT_ROOT / "jobs"),
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

API_HOST: str = os.getenv("EIKONA_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("EIKONA_PORT", "8000"))

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

WORKER_POLL_INTERVAL: float = float(os.getenv("EIKONA_WORKER_POLL", "0.5"))
