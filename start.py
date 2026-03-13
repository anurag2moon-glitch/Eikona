"""
start.py

Single command to spin up both the API server and the inference worker.

    python start.py                     # defaults
    python start.py --port 9000         # custom port
    python start.py --workers-only      # just the worker (no API)
    python start.py --api-only          # just the API (no worker)

Architecture:
    ┌────────────────────────────────────────────┐
    │  start.py (main process)                   │
    │                                            │
    │  ┌──────────────────┐  ┌────────────────┐  │
    │  │  API Server      │  │  Worker        │  │
    │  │  (subprocess)    │  │  (subprocess)  │  │
    │  │  uvicorn         │  │  consumer.py   │  │
    │  └──────────────────┘  └────────────────┘  │
    └────────────────────────────────────────────┘
"""

import os
import sys
import signal
import argparse
import subprocess
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(
        description="Eikona — Start API server and inference worker.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python start.py                          # Start both API + Worker
    python start.py --port 9000              # Custom port
    python start.py --api-only               # Only API (worker runs separately)
    python start.py --workers-only           # Only Worker
    EIKONA_CHECKPOINT=./checkpoints/G_epoch50.pth python start.py
        """,
    )
    parser.add_argument("--host", default="0.0.0.0", help="API host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--api-only", action="store_true", help="Start only the API server")
    parser.add_argument("--workers-only", action="store_true", help="Start only the worker")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    processes = []

    def shutdown(signum=None, frame=None):
        print("\n🛑 Shutting down...")
        for name, proc in processes:
            if proc.poll() is None:
                print(f"  Stopping {name} (PID {proc.pid})")
                proc.terminate()
        # Give them a moment, then force-kill
        time.sleep(1)
        for name, proc in processes:
            if proc.poll() is None:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    env = os.environ.copy()
    env["EIKONA_HOST"] = args.host
    env["EIKONA_PORT"] = str(args.port)
    env["PYTHONPATH"] = PROJECT_ROOT + ((":" + env.get("PYTHONPATH", "")) if env.get("PYTHONPATH") else "")
    
    # Fix for OpenMP Conflict on macOS
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"

    print("=" * 60)
    print("  🎨 Eikona — RAG-Guided Pix2Pix Server")
    print("=" * 60)

    # Start Worker
    if not args.api_only:
        print("  🔧 Starting Worker...")
        worker_cmd = [sys.executable, "-m", "worker.consumer"]
        worker_proc = subprocess.Popen(worker_cmd, cwd=PROJECT_ROOT, env=env)
        processes.append(("Worker", worker_proc))
        print(f"     PID: {worker_proc.pid}")

    # Start API
    if not args.workers_only:
        print(f"  🌐 Starting API on http://{args.host}:{args.port}")
        print(f"     📖 Docs:  http://localhost:{args.port}/docs")
        print(f"     📘 ReDoc: http://localhost:{args.port}/redoc")
        api_cmd = [
            sys.executable, "-m", "uvicorn",
            "api.main:app",
            "--host", args.host,
            "--port", str(args.port),
        ]
        if args.reload:
            api_cmd.append("--reload")
        api_proc = subprocess.Popen(api_cmd, cwd=PROJECT_ROOT, env=env)
        processes.append(("API", api_proc))
        print(f"     PID: {api_proc.pid}")

    print("=" * 60)
    print("  Press Ctrl+C to stop all services.")
    print("=" * 60)

    # Wait for any process to exit
    try:
        while True:
            for name, proc in processes:
                retcode = proc.poll()
                if retcode is not None:
                    print(f"\n⚠️  {name} exited with code {retcode}")
                    shutdown()
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
