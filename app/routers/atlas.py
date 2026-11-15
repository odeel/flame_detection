"""
FlameAtlas routes on this domain (prefix /api/v1/atlas). They follow the FlameAtlas API document one to one:

  GET  /atlas/habitats                    GET  /atlas/investigations          GET /atlas/investigation/{id}
  GET  /atlas/compare?ids=PSI-69,PSI-99    POST /atlas/rank                    POST /atlas/ask   (RAG, uses an LLM)
  POST /atlas/retrieve                     GET  /atlas/passage?id=...          POST /atlas/predict
  GET  /atlas/fuels                        GET  /atlas/status  (is FlameAtlas connected?)
  GET  /atlas/flammap/{habitat}?fuel=&n=   GET  /atlas/gaps/{habitat}?n=&explain=   POST /atlas/whatif
  GET  /atlas/graph                        GET  /atlas/graph/facts?q=          POST /atlas/ask  {"graph": true}
  POST /atlas/materials/upload (CSV)       GET  /atlas/materials/report/{name}  (HTML report)
  GET  /atlas/materials/report/{name}/pdf  (the same report as a PDF download)

Inputs are validated here, then forwarded; answers come back unchanged. See app/atlas.py.
"""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, HTTPException, Path, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import pdf
from ..atlas import AtlasError

router = APIRouter(prefix="/atlas", tags=["atlas"])

InvId = Annotated[str, Path(pattern=r"^PSI-\d{1,5}$", examples=["PSI-99"])]
HABITAT_ID = r"^[a-z][a-z0-9_]{1,39}$"
CRITERIA = ("flammability", "detection", "suppression", "physics", "closeness")


def atlas(req: Request):
    return req.app.state.atlas


async def forward(req: Request, method: str, path: str, *, params=None, body=None, cache=False, files=None, html=False):
    try:
        return await atlas(req).call(method, path, params=params, body=body, cache=cache, files=files, html=html)
    except AtlasError as e:
        raise HTTPException(e.status, e.message) from e


# ------------------------------------------------------------------ request bodies (mirror the FlameAtlas document)
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RankRequest(Strict):
    habitat_id: str = Field(..., pattern=HABITAT_ID, examples=["mars_base"])
    priorities: dict[str, float] | None = Field(None, description="Importance of each criterion: flammability, detection, suppression, physics, closeness",
                                                examples=[{"flammability": 3, "detection": 2, "suppression": 3, "physics": 1, "closeness": 3}])
    pairwise: list[list[float]] | None = Field(None, description="Instead of priorities: 5x5 AHP matrix in the order flammability, detection, suppression, physics, closeness")
    orness: float | None = Field(None, ge=0, le=1, examples=[0.5])
    top: int | None = Field(None, ge=1, le=50, examples=[5])

    @field_validator("priorities")
    @classmethod
    def _prio(cls, v):
        if v is not None:
            bad = set(v) - set(CRITERIA)
            if bad:
                raise ValueError(f"unknown criteria {sorted(bad)}; use {', '.join(CRITERIA)}")
            if any(x < 0 or x > 100 for x in v.values()):
                raise ValueError("priorities must be between 0 and 100")
        return v

    @field_validator("pairwise")
    @classmethod
    def _pair(cls, v):
        if v is not None and (len(v) != 5 or any(len(row) != 5 for row in v) or any(x <= 0 for row in v for x in row)):
            raise ValueError("pairwise must be a 5x5 matrix of positive numbers")
        return v


class AskRequest(Strict):
    question: str = Field(..., min_length=3, max_length=1000, examples=["Which materials were burned in the SAFFIRE-II experiment?"])
    habitat: str | None = Field(None, pattern=HABITAT_ID, examples=["mars_base"])
    k: int | None = Field(None, ge=1, le=20, examples=[5])
    inv_ids: list[Annotated[str, Field(pattern=r"^PSI-\d{1,5}$")]] | None = Field(None, max_length=24)
    check: bool | None = Field(None, description="Ask FlameAtlas to remove sentences the sources do not support")
    graph: bool | None = Field(None, description="Graph-RAG: add knowledge-graph facts as an extra source")


class RetrieveRequest(Strict):
    question: str = Field(..., min_length=3, max_length=1000)
    k: int | None = Field(None, ge=1, le=50)
    mode: Literal["dense", "keyword", "hybrid", "hybrid+rerank"] | None = None
    inv_ids: list[Annotated[str, Field(pattern=r"^PSI-\d{1,5}$")]] | None = Field(None, max_length=24)


class PredictRequest(Strict):
    fuel: str = Field(..., min_length=1, max_length=40, examples=["Heptane"])
    o2_pct: float | None = Field(None, gt=0, le=100, examples=[21])
    pressure_kpa: float | None = Field(None, gt=0, le=1000, examples=[101.3])
    habitat_id: str | None = Field(None, pattern=HABITAT_ID, description="Instead of o2_pct + pressure_kpa: use this habitat's air")
    co2_pct: float | None = Field(None, ge=0, le=100)
    he_pct: float | None = Field(None, ge=0, le=100)
    d0_mm: float | None = Field(None, gt=0, le=50)


class WhatIfRequest(Strict):
    """Values mode (free): habitat_id + changed values. Text mode (uses an LLM): text, e.g. "Mars base raises oxygen to 30 %"."""
    text: str | None = Field(None, min_length=3, max_length=500, examples=["Mars base raises oxygen to 30 %"])
    habitat_id: str | None = Field(None, pattern=HABITAT_ID, examples=["mars_base"])
    o2_pct: float | None = Field(None, gt=0, le=100)
    pressure_kpa: float | None = Field(None, gt=0, le=1000)
    co2_pct: float | None = Field(None, ge=0, le=100)
    he_pct: float | None = Field(None, ge=0, le=100)
    gravity_g: float | None = Field(None, ge=0, le=10)
    fuel: str | None = Field(None, min_length=1, max_length=40)
    explain: bool | None = None
    priorities: dict[str, float] | None = None
    orness: float | None = Field(None, ge=0, le=1)

    @field_validator("priorities")
    @classmethod
    def _prio(cls, v):
        if v is not None and (set(v) - set(CRITERIA) or any(x < 0 or x > 100 for x in v.values())):
            raise ValueError(f"priorities: use {', '.join(CRITERIA)}, each between 0 and 100")
        return v


def payload(m: BaseModel) -> dict:
    """Forward only the fields the caller sent, so FlameAtlas applies its own defaults."""
    return m.model_dump(exclude_unset=True)


# ------------------------------------------------------------------ routes
@router.get("/status", summary="Whether FlameAtlas is configured and reachable")
async def status(req: Request):
    return await atlas(req).status()


@router.get("/habitats", summary="Habitats with their cabin atmospheres (ISS, Gateway, Moon base, Mars base)")
async def habitats(req: Request):
    return await forward(req, "GET", "/habitats", cache=True)


@router.get("/investigations", summary="The 24 PSI investigations with plain-language summaries")
async def investigations(req: Request):
    return await forward(req, "GET", "/investigations", cache=True)


@router.get("/investigation/{inv_id}", summary="One investigation with its extracted experiment rows")
async def investigation(req: Request, inv_id: InvId):
    return await forward(req, "GET", f"/investigation/{inv_id}", cache=True)


@router.get("/compare", summary="Several investigations side by side (ids=PSI-69,PSI-99)")
async def compare(req: Request, ids: str = Query(..., pattern=r"^PSI-\d{1,5}(,PSI-\d{1,5}){1,5}$", examples=["PSI-69,PSI-99"])):
    return await forward(req, "GET", "/compare", params={"ids": ids}, cache=True)


@router.post("/rank", summary="Rank investigations for a habitat (AHP weights + OWA aggregation), with reasons")
async def rank(req: Request, body: RankRequest):
    # Without priorities or pairwise, FlameAtlas uses its default priorities.
    return await forward(req, "POST", "/rank", body=payload(body), cache=True)


@router.post("/ask", summary="Ask a question; answered from NASA PSI passages with citations (RAG, uses an LLM)")
async def ask(req: Request, body: AskRequest):
    ok, retry = req.app.state.limiter.check("atlas-ask:" + req.state.rate_key, limit=10)   # each new question costs LLM tokens
    if not ok:
        raise HTTPException(429, f"Too many questions; try again in {retry} s")
    return await forward(req, "POST", "/ask", body=payload(body))     # FlameAtlas caches answers itself


@router.post("/retrieve", summary="Search NASA PSI passages without an LLM (dense, keyword, hybrid, hybrid+rerank)")
async def retrieve(req: Request, body: RetrieveRequest):
    return await forward(req, "POST", "/retrieve", body=payload(body), cache=True)


@router.get("/passage", summary="Full source text of a passage (id like PSI-99::936617f3::0002)")
async def passage(req: Request, id: str = Query(..., pattern=r"^PSI-\d{1,5}::[0-9a-f]{4,64}::\d{1,6}$", examples=["PSI-99::936617f3::0002"])):
    return await forward(req, "GET", "/passage", params={"id": id}, cache=True)


@router.post("/predict", summary="Predict a droplet flame (extinction, fuel burned, burning rate) for a fuel and air, or a habitat")
async def predict(req: Request, body: PredictRequest):
    if body.habitat_id is None and (body.o2_pct is None or body.pressure_kpa is None):
        raise HTTPException(422, "Send o2_pct and pressure_kpa, or a habitat_id")
    return await forward(req, "POST", "/predict", body=payload(body), cache=True)


@router.get("/fuels", summary="Fuels the droplet prediction model supports")
async def fuels(req: Request):
    return await forward(req, "GET", "/fuels", cache=True)


def llm_limit(req: Request, what: str) -> None:
    """Calls that make FlameAtlas use its LLM cost money: the same budget as /ask (10 a minute per visitor)."""
    ok, retry = req.app.state.limiter.check("atlas-ask:" + req.state.rate_key, limit=10)
    if not ok:
        raise HTTPException(429, f"Too many {what}; try again in {retry} s")


HabitatId = Annotated[str, Path(pattern=HABITAT_ID, examples=["mars_base"])]


@router.get("/flammap/{habitat_id}", summary="Flammability map: predicted droplet-flame outcome over an O2 x pressure grid around a habitat")
async def flammap(req: Request, habitat_id: HabitatId, fuel: str = Query("Heptane", min_length=1, max_length=40),
                  n: int = Query(60, ge=10, le=120)):
    return await forward(req, "GET", f"/flammap/{habitat_id}", params={"fuel": fuel, "n": n}, cache=True)


@router.get("/gaps/{habitat_id}", summary="Test gaps: conditions near a habitat that no NASA test covered (explain=true uses an LLM)")
async def gaps(req: Request, habitat_id: HabitatId, n: int = Query(10, ge=1, le=30), explain: bool = False):
    if explain:
        llm_limit(req, "explanations")
    return await forward(req, "GET", f"/gaps/{habitat_id}", params={"n": n, "explain": str(explain).lower()}, cache=True)


@router.post("/whatif", summary="What if a habitat's air changes? Values mode is free; text mode uses an LLM")
async def whatif(req: Request, body: WhatIfRequest):
    if body.text:
        llm_limit(req, "questions")
    elif body.habitat_id is None:
        raise HTTPException(422, "Send a habitat_id with the values to change, or a text question")
    return await forward(req, "POST", "/whatif", body=payload(body), cache=True)


# ------------------------------------------------------------------ knowledge graph, materials analysis
GRAPH_TYPES = {"investigation", "platform", "finding", "material", "diluent", "instrument", "condition", "phenomenon"}
MAX_UPLOAD = 5 * 1024 * 1024                         # FlameAtlas's own limit: 5 MB, 200 rows
UPLOAD_TYPES = (".csv", ".tsv", ".txt")
# The report is FlameAtlas's page (it contains uploaded text): no scripts, no outside requests, sandboxed.
REPORT_CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; base-uri 'none'; "
              "form-action 'none'; sandbox allow-popups allow-popups-to-escape-sandbox")


@router.get("/graph", summary="Knowledge graph (investigations, materials, diluents, instruments, findings...): nodes and edges")
async def graph(req: Request,
                entity: str | None = Query(None, min_length=1, max_length=80, pattern=r"^[\w .:+()/,%*-]+$", examples=["helium"]),
                investigation: str | None = Query(None, pattern=r"^PSI-\d{1,5}$", examples=["PSI-99"]),
                types: str | None = Query(None, max_length=120, examples=["material,diluent"]),
                findings: bool | None = None, radius: int | None = Query(None, ge=1, le=2)):
    if types:
        bad = set(t.strip() for t in types.split(",")) - GRAPH_TYPES
        if bad:
            raise HTTPException(422, f"unknown node types {sorted(bad)}; use {', '.join(sorted(GRAPH_TYPES))}")
    params = {k: v for k, v in {"entity": entity, "investigation": investigation, "types": types, "radius": radius,
                                "findings": None if findings is None else str(findings).lower()}.items() if v is not None}
    return await forward(req, "GET", "/graph", params=params or None, cache=True)


@router.get("/graph/facts", summary="Knowledge-graph facts for a question (what Graph-RAG adds to /ask)")
async def graph_facts(req: Request, q: str = Query(..., min_length=3, max_length=500, examples=["Which fuels were tested both with CO2 and helium?"])):
    return await forward(req, "GET", "/graph/facts", params={"q": q}, cache=True)


@router.post("/materials/upload", summary="Fire-risk analysis of a materials CSV (one row per material, an 'id' column); uses an LLM for new rows")
async def materials_upload(req: Request, file: UploadFile = File(..., description="CSV, max 5 MB and 200 rows"), report: bool = True):
    name = (file.filename or "materials.csv").replace("\\", "/").rsplit("/", 1)[-1][:100] or "materials.csv"
    if not name.lower().endswith(UPLOAD_TYPES):
        raise HTTPException(422, "Upload a .csv file (comma, semicolon or tab separated)")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "The file is larger than 5 MB")
    if not data.strip():
        raise HTTPException(422, "The file is empty")
    ok, retry = req.app.state.limiter.check("atlas-materials:" + req.state.rate_key, limit=3)   # up to 200 LLM rows each
    if not ok:
        raise HTTPException(429, f"Too many uploads; try again in {retry} s")
    llm_limit(req, "uploads")
    return await forward(req, "POST", "/materials/upload", params={"report": str(report).lower()},
                         files={"file": (name, data, "text/csv")})


@router.get("/materials/report/{name}", response_class=HTMLResponse,
            summary="HTML report of an upload (summary cards, charts, materials table)")
async def materials_report(req: Request, name: Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")]):
    if ".." in name:
        raise HTTPException(422, "invalid report name")
    page = await forward(req, "GET", f"/materials/report/{name}", cache=True, html=True)
    if not isinstance(page, str):
        raise HTTPException(502, "FlameAtlas did not return a report page")
    return HTMLResponse(page, headers={"Content-Security-Policy": REPORT_CSP, "X-Frame-Options": "SAMEORIGIN",
                                       "Cache-Control": "private, max-age=300"})


@router.get("/materials/report/{name}/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}, "description": "The report as a PDF file (report-name-fire-risk-report.pdf)"}},
            summary="The materials risk report as a downloadable PDF")
async def materials_report_pdf(req: Request, name: Annotated[str, Path(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")],
                               download: Annotated[bool, Query(description="true: ask the browser to save the file instead of opening it")] = False):
    if ".." in name:
        raise HTTPException(422, "invalid report name")
    if not pdf.is_cached(name):                                    # only new conversions count: each one starts a browser
        ok, retry = req.app.state.limiter.check("atlas-pdf:" + req.state.rate_key, limit=10)
        if not ok:
            raise HTTPException(429, f"Too many PDF downloads; try again in {retry} s")
    page = await forward(req, "GET", f"/materials/report/{name}", cache=True, html=True)
    if not isinstance(page, str):
        raise HTTPException(502, "FlameAtlas did not return a report page")
    try:
        data = await pdf.html_to_pdf(page, key=name)
    except pdf.PdfUnavailable as e:
        raise HTTPException(503, str(e)) from e
    # No Content-Disposition by default: Microsoft Edge answers a page's fetch() of a binary response that carries one
    # (attachment or inline) with an empty 204, so the dashboard fetches the PDF and saves it under its own name.
    # ?download=true adds "attachment" for plain links that should save the file.
    headers = {"Cache-Control": "private, max-age=300"}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{name}-fire-risk-report.pdf"'
    return Response(data, media_type="application/pdf", headers=headers)
