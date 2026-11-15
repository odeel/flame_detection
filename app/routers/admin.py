"""Admin routes (FIF_ADMIN_TOKEN or an admin API key; localhost only when no token is configured)."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ..schemas import DocumentIngestRequest
from ..services import JobConflict

router = APIRouter(prefix="/admin", tags=["admin"])


async def admin(req: Request):
    return await req.app.state.auth.require_admin(req)


def _background(req: Request, kind: str, fn):
    """Start a tracked job in the background and return 202 with its id (poll GET /admin/jobs)."""
    s = req.app.state.services
    tasks: set = req.app.state.tasks

    async def run():
        try:
            await s.run_job(kind, fn)
        except JobConflict:
            pass

    t = asyncio.create_task(run())
    tasks.add(t)
    t.add_done_callback(tasks.discard)
    return {"accepted": True, "kind": kind, "poll": "/api/v1/admin/jobs"}


@router.post("/documents/ingest", status_code=202, dependencies=[Depends(admin)],
             summary="Download PSI PDF documents (resumable), parse them into page passages and index them")
async def ingest_documents(req: Request, body: DocumentIngestRequest = Body(default_factory=DocumentIngestRequest)):
    s = req.app.state.services
    if await _running(s, "documents"):
        raise HTTPException(409, "A documents job is already running")
    return _background(req, "documents", lambda: s.ingest_documents(accessions=body.accessions, categories=body.categories, max_mb=body.max_mb, limit=body.limit))


@router.post("/documents/reindex", status_code=202, dependencies=[Depends(admin)], summary="Re-parse PDFs already on disk (no network)")
async def reindex(req: Request):
    s = req.app.state.services
    return _background(req, "documents", s.index_local_documents)


@router.post("/derived/rebuild", dependencies=[Depends(admin)], summary="Rebuild test rows, metadata passages, summaries and briefs now")
async def rebuild(req: Request):
    return await req.app.state.services.ensure_derived(force=True)


@router.post("/summaries/regenerate", status_code=202, dependencies=[Depends(admin)],
             summary="Regenerate stored summaries and briefs; claude=true adds grounded LLM summaries (needs ANTHROPIC_API_KEY)")
async def regenerate(req: Request, claude: bool = False):
    s = req.app.state.services
    if claude and not s.claude:
        raise HTTPException(503, "Set ANTHROPIC_API_KEY to generate LLM summaries")

    async def go():
        out = {"extractive": await s.regenerate_summaries()}
        if claude:
            out["claude"] = await s.claude_summaries()
        return out
    return _background(req, "summaries", go)


@router.post("/cache/clear", dependencies=[Depends(admin)], summary="Clear the response cache")
async def clear(req: Request):
    n = req.app.state.services.cache.clear()
    return {"cleared": n, "responses": n, "atlas": req.app.state.atlas.clear()}


@router.post("/train", dependencies=[Depends(admin)], summary="Retrain all models on the PSI data in PostgreSQL (runs scripts/train.mjs)")
async def train(req: Request):
    try:
        return {"models": await req.app.state.services.train_models()}
    except RuntimeError as e:
        raise HTTPException(503 if "Node.js" in str(e) else 500, str(e)) from e


@router.post("/ingest", dependencies=[Depends(admin)],
             summary="Pull the live NASA PSI catalog into PostgreSQL, then retrain models (runs scripts/fetch-psi.mjs)")
async def ingest(req: Request):
    try:
        return await req.app.state.services.ingest_psi()
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e


@router.get("/jobs", dependencies=[Depends(admin)], summary="Recent jobs (ingest, train, documents, summaries)")
async def jobs(req: Request, limit: int = 30):
    async with req.app.state.services.pool.connection() as c:
        rows = await (await c.execute("SELECT id, kind, status, started_at, finished_at, detail FROM jobs ORDER BY id DESC LIMIT %s", (min(limit, 200),))).fetchall()
    return {"items": rows}


async def _running(s, kind: str) -> bool:
    async with s.pool.connection() as c:
        return bool(await (await c.execute("SELECT 1 FROM jobs WHERE kind = %s AND status = 'running'", (kind,))).fetchone())
