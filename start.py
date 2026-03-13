import os
import sys
import signal
import argparse
import subprocess
import time
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv() # Load root .env

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def push_to_firebase(url):
    db_url = os.getenv("FIREBASE_DATABASE_URL")
    if not db_url:
        print("  ⚠️  FIREBASE_DATABASE_URL not set in .env")
        return
    
    # Ensure URL ends without trailing slash for the path
    db_url = db_url.rstrip("/")
    endpoint = f"{db_url}/server_config.json"
    
    try:
        data = {"api_url": url, "updated_at": int(time.time())}
        response = requests.patch(endpoint, json=data)
        if response.status_code == 200:
            print(f"  🔥 Successfully synced Cloudflare URL to Firebase.")
        else:
            print(f"  ⚠️  Firebase sync failed with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"  ⚠️  Firebase sync error: {e}")


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
    parser.add_argument("--tunnel", action="store_true", help="Start a Cloudflare tunnel")
    args = parser.parse_args()

    processes = []

    def update_frontend_env(url):
        env_path = os.path.join(PROJECT_ROOT, "frontend", ".env.local")
        try:
            with open(env_path, "w") as f:
                f.write(f"NEXT_PUBLIC_API_URL={url}\n")
            print(f"  📝 Updated frontend/.env.local with {url}")
        except Exception as e:
            print(f"  ⚠️  Failed to update frontend/.env.local: {e}")

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

    # Start Tunnel if requested
    if args.tunnel:
        print("  ☁️  Starting Cloudflare Tunnel...")
        try:
            # Check for local binary first
            local_bin = os.path.join(PROJECT_ROOT, "cloudflared")
            binary = local_bin if os.path.exists(local_bin) else "cloudflared"
            
            # We use --url to start an ephemeral tunnel
            tunnel_cmd = [binary, "tunnel", "--url", f"http://localhost:{args.port}"]
            # We need to capture stderr because cloudflared logs there
            tunnel_proc = subprocess.Popen(
                tunnel_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                bufsize=1,
                env=env
            )
            processes.append(("Tunnel", tunnel_proc))
            
            # Non-blocking check for the URL
            tunnel_url = None
            start_time = time.time()
            print("     Waiting for tunnel URL...")
            
            # Read stderr line by line until we find the URL or timeout
            if tunnel_proc.stderr:
                import re
                url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
                
                while time.time() - start_time < 30:
                    line = tunnel_proc.stderr.readline()
                    if not line:
                        break
                    match = url_pattern.search(line)
                    if match:
                        tunnel_url = match.group(0)
                        print(f"     ✅ Tunnel Live: {tunnel_url}")
                        update_frontend_env(tunnel_url)
                        push_to_firebase(tunnel_url)
                        break
            
            if not tunnel_url:
                print("     ⚠️  Could not find tunnel URL in logs.")
        except FileNotFoundError:
            print("     ❌ Error: 'cloudflared' binary not found. Please install it first.")
            print("        brew install cloudflare/cloudflare/cloudflared")
        except Exception as e:
            print(f"     ❌ Tunnel Error: {e}")

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
                # Special handling for Tunnel since we are reading its stderr in a thread-like way
                # but for now just poll and check if it crashed
                retcode = proc.poll()
                if retcode is not None:
                    # If tunnel exits but we want it to stay, report error
                    if name == "Tunnel":
                        print(f"\n⚠️  {name} exited unexpectedly with code {retcode}")
                        # Optional: Print last few lines of stderr for debugging
                    else:
                        print(f"\n⚠️  {name} exited with code {retcode}")
                        shutdown()
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
