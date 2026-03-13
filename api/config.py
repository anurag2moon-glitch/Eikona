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

def get_latest_checkpoint():
    ckpt_dir = PROJECT_ROOT / "checkpoints"
    if not ckpt_dir.exists():
        return None
    
    # Look for G_epochX.pth files
    import re
    checkpoints = []
    for f in ckpt_dir.glob("G_epoch*.pth"):
        match = re.search(r"G_epoch(\d+)\.pth", f.name)
        if match:
            checkpoints.append((int(match.group(1)), str(f)))
            
    if not checkpoints:
        # Fallback to any .pth file if no epoch-named ones exist
        all_pths = list(ckpt_dir.glob("*.pth"))
        return str(all_pths[0]) if all_pths else None
        
    # Return the one with highest epoch number
    checkpoints.sort(key=lambda x: x[0], reverse=True)
    return checkpoints[0][1]

# Automatic checkpoint discovery
_detected_ckpt = get_latest_checkpoint()
CHECKPOINT_PATH: str = os.getenv(
    "EIKONA_CHECKPOINT",
    _detected_ckpt or str(PROJECT_ROOT / "checkpoints" / "G_epoch1.pth"),
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
