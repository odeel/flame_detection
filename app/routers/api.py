"""Public API routes (prefix /api/v1). Every response is computed from NASA PSI data stored in PostgreSQL."""
from __future__ import annotations

import csv
import io
import json
import time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse

from .. import brief as brief_mod
from .. import store, summaries
from ..habitats import BY_ID, HABITATS, PILLARS
from ..schemas import AskRequest, HabitatId, Pillar, RankRequest

router = APIRouter()
Accession = Annotated[str, Path(pattern=r"^PSI-\d{1,5}$", examples=["PSI-69"])]


def svc(req: Request):
    return req.app.state.services


# ------------------------------------------------------------------ system
@router.get("/livez", tags=["system"], summary="Liveness and readiness (one database round-trip)")
async def livez(req: Request):
    try:
        async with svc(req).pool.connection() as c:
            await c.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:  # pragma: no cover - exercised when the database is down
        raise HTTPException(503, "database unreachable") from e


@router.get("/health", tags=["system"], summary="Service health, data counts, caches and AI configuration")
async def health(req: Request):
    s = svc(req)
    t0 = time.perf_counter()
    async with s.pool.connection() as c:
        version = (await (await c.execute("SHOW server_version")).fetchone())["server_version"]
        migrations = [r["name"] for r in await (await c.execute("SELECT name FROM schema_migrations ORDER BY version")).fetchall()]
        fetched = await store.get_meta(c, "psi_fetched_at", "")
    latency = (time.perf_counter() - t0) * 1000
    counts = await s.cached("health_counts", lambda: store.psi_counts(s.pool))
    st = s.pool.get_stats()
    return {"status": "ok", "version": req.app.version, "uptimeSeconds": round(time.time() - s.started),
            "data": {"psiFetchedAt": fetched, "generation": await s.generation(), **counts},
            "database": {"engine": "PostgreSQL", "version": version, "latencyMs": round(latency, 2), "migrations": migrations,
                         "pool": {"size": st.get("pool_size"), "available": st.get("pool_available"), "waiting": st.get("requests_waiting", 0)}},
            "cache": s.cache.stats(),
            "ai": {"retrieval": "hybrid BM25 + PostgreSQL full-text", "llm": s.settings.claude_model if s.claude else None,
                   "llmEnabled": bool(s.claude), "pdfParser": "poppler pdftotext"},
            "claude": {"enabled": bool(s.claude), "model": s.settings.claude_model if s.claude else None},
            "models": [{"id": a["id"], "version": a["version"], "algorithm": a["algorithm"]} for a in await s.active_models()],
            "predictionsServed": await s.prediction_count(),
            "auth": {"you": req.state.principal["role"], "adminTokenConfigured": bool(s.settings.admin_token)}}


# ------------------------------------------------------------------ habitats
@router.get("/habitats", tags=["habitats"], summary="Crew environments with design atmospheres and evidence coverage")
async def habitats(req: Request):
    s = svc(req)

    async def go():
        out = []
        for h in HABITATS:
            r = await s.rank(h["id"], limit=100)
            items = r["items"]
            out.append({**h, "evidence": {"investigationsAtAtmosphere": sum(1 for i in items if i["components"]["atmosphere"] == 1.0),
                                          "investigationsAtOrAboveO2": sum(1 for i in items if i["components"]["atmosphere"] >= 0.65)},
                        "top": [{"accession": i["accession"], "acronym": i["acronym"], "score": i["score"]} for i in items[:3]]})
        return out
    return {"items": await s.cached("habitats", go), "pillars": PILLARS}


@router.get("/habitats/{habitat}", tags=["habitats"], summary="One habitat: ranked investigations with rubric components and reasons")
async def habitat(req: Request, habitat: HabitatId, limit: int = Query(10, ge=1, le=100)):
    r = await svc(req).rank(habitat, limit=limit)
    return {"habitat": BY_ID[habitat], "weights": r["weights"], "total": r["total"], "items": r["items"]}


# ------------------------------------------------------------------ investigations and ranking
@router.get("/investigations", tags=["investigations"], summary="PSI combustion investigations, ranked (optionally for a habitat)")
async def investigations(req: Request, habitat: HabitatId | None = None, pillar: Pillar | None = None,
                         q: str | None = Query(None, max_length=200, description="Topic query (BM25 over PSI text)"), limit: int = Query(50, ge=1, le=100)):
    r = await svc(req).rank(habitat, query=q, pillar=pillar, limit=limit)
    return {"habitat": habitat, "weights": r["weights"], "total": r["total"],
            "items": [{k: i[k] for k in ("rank", "accession", "acronym", "title", "score", "pillars", "envelope", "doi")} for i in r["items"]]}


@router.get("/investigations/{accession}", tags=["investigations"], summary="One investigation: PSI record, stored summaries, test envelope, documents")
async def investigation(req: Request, accession: Accession):
    s = svc(req)

    async def go():
        async with s.pool.connection() as c:
            row = await (await c.execute("SELECT accession, acronym, title, platform, doc FROM psi_investigations WHERE accession = %s", (accession,))).fetchone()
            if not row:
                return None
            tables = await (await c.execute('SELECT id, label, file, row_count AS "rowCount" FROM psi_tables WHERE accession = %s ORDER BY id', (accession,))).fetchall()
        stats = (await store.test_stats(s.pool)).get(accession)
        sums = await summaries.get(s.pool, "investigation", accession)
        docs = await store.documents(s.pool, accession)
        per_habitat = {}
        for h in HABITATS:
            r = await s.rank(h["id"], limit=100)
            hit = next((i for i in r["items"] if i["accession"] == accession), None)
            if hit:
                per_habitat[h["id"]] = {"rank": hit["rank"], "score": hit["score"], "components": hit["components"], "reasons": hit["reasons"]}
        return {"record": row["doc"] | {"accession": accession}, "summary": sums[0]["content"] if sums else None,
                "summaries": [{"generator": x["generator"], "createdAt": x["createdAt"]} for x in sums], "tables": tables,
                "testEnvelope": stats, "documents": docs, "habitats": per_habitat}
    out = await s.cached(f"inv|{accession}", go)
    if out is None:
        raise HTTPException(404, "PSI investigation not found")
    return out


@router.post("/rank", tags=["investigations"], summary="Rank investigations by the transparent rubric (habitat, weights, filters)")
async def rank(req: Request, body: RankRequest):
    w = body.weights.model_dump(exclude_none=True) if body.weights else None
    return await svc(req).rank(body.habitat, w, body.query, body.pillar, body.min_tests, body.limit)


# ------------------------------------------------------------------ tests


def _filters(fuel, o2, o2_tol, o2_min, o2_max, pressure_min, pressure_max, flow_min, flow_max, outcome, accession, diluent):
    return dict(fuel=fuel, o2=o2, o2_tol=o2_tol, o2_min=o2_min, o2_max=o2_max, pressure_min=pressure_min, pressure_max=pressure_max,
                flow_min=flow_min, flow_max=flow_max, outcome=outcome, accession=accession, diluent=diluent)


@router.get("/tests", tags=["tests"], summary="Normalized ISS test rows: filter by fuel, O2, pressure, flow, outcome")
async def tests(req: Request,
                fuel: str | None = Query(None, max_length=80, description="Substring, case-insensitive (e.g. ethylene, PMMA, methanol)"),
                o2: float | None = Query(None, gt=0, le=100, description="O2 vol %; matches within o2_tol"),
                o2_tol: float = Query(1.0, ge=0, le=50),
                o2_min: float | None = Query(None, ge=0, le=100), o2_max: float | None = Query(None, ge=0, le=100),
                pressure_min: float | None = Query(None, ge=0, description="kPa"), pressure_max: float | None = Query(None, ge=0),
                flow_min: float | None = Query(None, ge=0, description="cm/s"), flow_max: float | None = Query(None, ge=0),
                outcome: str | None = Query(None, max_length=80, description="Substring of the outcome text, e.g. 'Hot ignition: Yes'"),
                accession: str | None = Query(None, pattern=r"^PSI-\d{1,5}$"),
                diluent: Literal["CO2", "He", "N2"] | None = None,
                limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    f = _filters(fuel, o2, o2_tol, o2_min, o2_max, pressure_min, pressure_max, flow_min, flow_max, outcome, accession, diluent)
    s = svc(req)
    return await s.cached("tests|" + json.dumps(f, sort_keys=True) + f"|{limit}|{offset}", lambda: s.tests(**f, limit=limit, offset=offset))


@router.get("/tests/facets", tags=["tests"], summary="Fuels, diluents, ranges and per-investigation counts of the test rows")
async def test_facets(req: Request):
    return await svc(req).test_facets()


@router.get("/tests.csv", tags=["tests"], summary="Download filtered test rows as CSV (streamed)")
async def tests_csv(req: Request, fuel: str | None = Query(None, max_length=80), o2_min: float | None = Query(None, ge=0, le=100),
                    o2_max: float | None = Query(None, ge=0, le=100), pressure_min: float | None = Query(None, ge=0), pressure_max: float | None = Query(None, ge=0),
                    outcome: str | None = Query(None, max_length=80), accession: str | None = Query(None, pattern=r"^PSI-\d{1,5}$")):
    s = svc(req)
    f = _filters(fuel, None, 1.0, o2_min, o2_max, pressure_min, pressure_max, None, None, outcome, accession, None)
    cols = ["accession", "acronym", "table", "rowIndex", "fuel", "o2Pct", "pressureKpa", "flowCmS", "gravityG", "diluents", "conditions", "outcome", "measures"]

    async def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        offset = 0
        while True:
            page = await s.tests(**f, limit=1000, offset=offset)
            for r in page["items"]:
                w.writerow([json.dumps(r[c]) if isinstance(r[c], dict) else r[c] for c in cols])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate()
            offset += 1000
            if offset >= page["total"]:
                break
    return StreamingResponse(gen(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="flame-in-freefall-tests.csv"', "Cache-Control": "no-store"})


# ------------------------------------------------------------------ ask
@router.post("/ask", tags=["ask"], summary="Cited answer from NASA PSI documents (retrieval-augmented; never invents numbers)")
async def ask(req: Request, body: AskRequest):
    limiter = req.app.state.limiter
    ok, retry = limiter.check("ask:" + req.state.rate_key, limit=30)
    if not ok:
        raise HTTPException(429, f"Too many questions; retry in {retry} s")
    s = svc(req)
    key = "ask|" + body.model_dump_json()
    return await s.cached(key, lambda: s.ask(body.question, body.habitat, body.accessions, body.k, body.mode))


# ------------------------------------------------------------------ briefs and summaries
@router.get("/brief/{habitat}", tags=["briefs"], summary="Printable fire-safety brief for a habitat (json, md or html)",
            responses={200: {"content": {"text/html": {}, "text/markdown": {}}}})
async def brief(req: Request, habitat: HabitatId, format: Literal["json", "md", "html"] = "json",
                fresh: bool = Query(False, description="Recompute instead of serving the stored, pre-generated brief")):
    s = svc(req)
    b = None
    if not fresh:
        stored = await summaries.get(s.pool, "brief", habitat)
        if stored and stored[0]["dataGeneration"] == await s.generation():
            b = stored[0]["content"]
    if b is None:
        b = await s.cached(f"brief|{habitat}", lambda: s.build_brief(habitat))
    if format == "md":
        return PlainTextResponse(brief_mod.to_markdown(b), media_type="text/markdown; charset=utf-8")
    if format == "html":
        return HTMLResponse(brief_mod.to_html(b))
    return b


@router.get("/summaries/{accession}", tags=["briefs"], summary="Pre-generated summaries of an investigation (all generators)")
async def get_summaries(req: Request, accession: Accession):
    rows = await summaries.get(svc(req).pool, "investigation", accession)
    if not rows:
        raise HTTPException(404, "No summary for this investigation")
    return {"accession": accession, "items": rows}


# ------------------------------------------------------------------ documents
@router.get("/documents", tags=["documents"], summary="Parsed NASA PSI documents and metadata records")
async def documents(req: Request, accession: str | None = Query(None, pattern=r"^PSI-\d{1,5}$"), kind: Literal["pdf", "metadata"] | None = None):
    s = svc(req)
    items = await s.cached(f"docs|{accession}", lambda: store.documents(s.pool, accession))
    if kind:
        items = [d for d in items if d["kind"] == kind]
    return {"total": len(items), "items": items}


@router.get("/documents/{accession}/{file_name}/pages/{page}", tags=["documents"], summary="Passages of one document page (to check a citation)")
async def document_page(req: Request, accession: Accession, file_name: str, page: int = Path(ge=1, le=5000)):
    async with svc(req).pool.connection() as c:
        rows = await (await c.execute("SELECT chunk_index AS \"chunkIndex\", section, text FROM doc_chunks WHERE document_id = %s AND page = %s ORDER BY chunk_index",
                                      (f"{accession}/{file_name}", page))).fetchall()
    if not rows:
        raise HTTPException(404, "No passages for this document page")
    return {"documentId": f"{accession}/{file_name}", "page": page, "passages": rows}
