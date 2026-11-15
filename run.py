"""
Start the API and the dashboard (run from backend-fastapi/):

  python run.py                 # http://127.0.0.1:8000   (your friends' React dashboard at /, classic at /classic)
  python run.py --port 9000 --reload
  python run.py --no-build      # skip (re)building the React dashboard

Before starting, the React dashboard is (re)built from its own folder (FIF_FRONTEND_DIR in backend-fastapi/.env)
into <repo>/ui-dist when it was never built or one of its files changed. Its folder is only read, never changed.

On Windows, psycopg's async mode cannot use the default ProactorEventLoop, and a plain
`uvicorn app.main:app` keeps that loop, so the database pool never connects. This script
switches to the selector loop before uvicorn creates its event loop.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import uvicorn

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "ui-dist"
SOURCE_TYPES = {".js", ".jsx", ".css", ".html", ".json"}


def frontend_dir() -> Path | None:
    """FIF_FRONTEND_DIR from the environment or backend-fastapi/.env."""
    value = os.environ.get("FIF_FRONTEND_DIR", "")
    env = Path(__file__).resolve().parent / ".env"
    if not value and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("FIF_FRONTEND_DIR="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
    return Path(value) if value else None


def fingerprint(front: Path) -> str:
    """Hash of every source file's path, size and date: any change (even files copied in with older dates) rebuilds."""
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(front)):
        dirs[:] = sorted(d for d in dirs if d not in ("node_modules", "dist", ".git"))
        for f in sorted(files):
            p = Path(root) / f
            if p.suffix in SOURCE_TYPES or f.startswith(".env"):
                st = p.stat()
                h.update(f"{p.relative_to(front)}|{st.st_size}|{int(st.st_mtime)}\n".encode())
    return h.hexdigest()


def build_dashboard() -> None:
    front = frontend_dir()
    if not front:
        return
    if not (front / "package.json").exists():
        print(f"[dashboard] FIF_FRONTEND_DIR does not point to the React dashboard ({front}): showing the classic dashboard.")
        return
    built, stamp, fp = DIST / "index.html", DIST / ".source-fingerprint", fingerprint(front)
    if built.exists() and stamp.exists() and stamp.read_text().strip() == fp:
        print("[dashboard] React dashboard is up to date.")
        return
    npm, npx = shutil.which("npm"), shutil.which("npx")
    if not (npm and npx):
        print("[dashboard] Node.js not found: cannot build the React dashboard (install Node.js 22+).")
        return
    if not (front / "node_modules" / "vite").exists():
        print(f"[dashboard] Installing the React dashboard's packages in {front} ...")
        subprocess.run([npm, "ci", "--no-fund", "--no-audit"], cwd=front, check=True)
    print(f"[dashboard] Building the React dashboard from {front} ...")
    # "/." makes the app call this same server (its api.js uses BASE + "/api/..."; "/./api/..." resolves to "/api/...").
    env = {**os.environ, "VITE_API_URL": "/."}
    subprocess.run([npx, "vite", "build", "--outDir", str(DIST), "--emptyOutDir", "--assetsDir", "ui-assets", "--logLevel", "warn"],
                   cwd=front, env=env, check=True)
    stamp.write_text(fp)
    print("[dashboard] Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run the Flame in Freefall FastAPI backend and dashboard")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.add_argument("--no-build", action="store_true", help="do not (re)build the React dashboard")
    args = p.parse_args()

    if not args.no_build:
        try:
            build_dashboard()
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"[dashboard] Build failed ({e}); the server starts with the last build or the classic dashboard.")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    print(f"Dashboard: http://{args.host}:{args.port}/   (classic dashboard: /classic, API docs: /docs)")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)
