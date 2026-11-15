"""
Routes for the React dashboard ("flame-detection-frontend"), exactly as its DATA_CONTRACT.md asks (prefix /api):

  GET    /api/investigations                 curated catalog (28) + NASA PSI DOI, link, data size, measured ranges
  GET    /api/investigations/{id}/tests      one row per test run, from the normalized PSI test matrices
  GET    /api/habitats                       crew habitats and their design atmospheres
  POST   /api/chat                           RAG answer with citations (FlameAtlas when reachable, else the local RAG)
  GET    /api/conversations                  the signed-in user's chats   GET/DELETE /api/conversations/{id}
  POST   /api/auth/signup | /api/auth/login  accounts with a role (researcher | engineer | student); bearer token
  GET    /api/auth/me    POST /api/auth/logout
  GET    /api/kpis?role=                     headline numbers computed from the database

Errors use {"error": "message", "code": "..."}. The role is checked on the server: a token's account role must
match the role a request names (403 otherwise). Unknown values are null, never missing.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from ..accounts import AccountError
from ..atlas import AtlasError
from ..habitats import HABITATS
from ..store import test_stats
from .auth import COOKIE, base_url, limit

router = APIRouter(prefix="/api", tags=["frontend"])
Role = Literal["researcher", "engineer", "student"]
CATALOG_FILE = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
KPA_TO_PSI = 0.1450377
NO_STORE = {"Cache-Control": "no-store", "Vary": "Authorization, Cookie"}
# Our habitat ids -> FlameAtlas habitat ids (its document: iss, gateway, moon_base, mars_base)
ATLAS_HABITAT = {"spacecraft": "iss", "station": "iss", "moonbase": "moon_base", "rover": "moon_base", "marsbase": "mars_base"}


# ------------------------------------------------------------------ catalog seeding (called at startup)
async def seed_catalog(pool) -> int:
    """Upsert app/data/catalog.json into catalog_investigations (ids missing from the file are removed)."""
    if not CATALOG_FILE.exists():
        return 0
    items = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))["items"]
    async with pool.connection() as c, c.transaction():
        for it in items:
            await c.execute("""INSERT INTO catalog_investigations (id, psi_accession, doc) VALUES (%s, %s, %s)
                               ON CONFLICT (id) DO UPDATE SET psi_accession = EXCLUDED.psi_accession, doc = EXCLUDED.doc, updated_at = now()
                               WHERE catalog_investigations.doc IS DISTINCT FROM EXCLUDED.doc""", (it["id"], it.get("psiAccession"), Jsonb(it)))
        await c.execute("DELETE FROM catalog_investigations WHERE NOT (id = ANY(%s))", ([it["id"] for it in items],))
    return len(items)


# ------------------------------------------------------------------ helpers
def svc(req: Request):
    return req.app.state.services


def fail(status: int, message: str, code: str | None = None):
    raise HTTPException(status, message, headers={"X-Error-Code": code} if code else None)


async def current_user(req: Request, required: bool = True) -> dict | None:
    """The signed-in account: bearer token (Authorization: Bearer <token>) or the dashboard's session cookie."""
    p = getattr(req.state, "principal", {}) or {}
    user = p.get("user")
    if not user:
        token = req.cookies.get(COOKIE, "")
        user = await req.app.state.accounts.session_user(token) if token else None
    if required and not user:
        fail(401, "Sign in first (send Authorization: Bearer <token> from /api/auth/login).", "unauthorized")
    return user


def check_role(user: dict | None, role: str | None) -> None:
    if user and role and user["profile"] != role:
        fail(403, f"This account's role is {user['profile']}, not {role}.", "role_mismatch")


def public_user(u: dict) -> dict:
    return {"id": u["id"], "email": u["email"], "name": u.get("name") or "", "role": u.get("profile", "researcher"), "verified": u.get("verified", False)}


def psi(v):
    return None if v is None else round(v * KPA_TO_PSI, 2)


def habitat_id(value: str | None) -> str | None:
    """Accept our habitat id or label ("Lunar surface base"), or the React dashboard's names ("Spacecraft / ISS",
    "Lunar base / rover", "EVA spacesuit"), case-insensitive."""
    if not value:
        return None
    v = value.strip().lower()
    for h in HABITATS:
        if v in (h["id"], h["label"].lower()) or v in h["examples"].lower():
            return h["id"]
    for pattern, hid in HABITAT_WORDS:
        if re.search(pattern, v):
            return hid
    return None


# Keyword fallback, most specific first ("Lunar base / rover" is the Moon base; "Spacecraft / ISS" the station).
HABITAT_WORDS = [(r"\beva\b|suit|airlock", "spacesuit"), (r"mars|martian", "marsbase"), (r"lunar|moon", "moonbase"), (r"rover", "rover"),
                 (r"\biss\b|station|gateway", "station"), (r"spacecraft|capsule|orion|artemis", "spacecraft")]


async def curated_of(pool) -> dict[str, str]:
    """PSI accession -> curated id (for citations and links)."""
    async with pool.connection() as c:
        rows = await (await c.execute("SELECT id, psi_accession FROM catalog_investigations WHERE psi_accession IS NOT NULL")).fetchall()
    return {r["psi_accession"]: r["id"] for r in rows}


# ------------------------------------------------------------------ 1. investigations
@router.get("/investigations", summary="Investigation catalog in the dashboard's shape")
async def investigations(req: Request):
    s = svc(req)
    return await s.cached("fe:investigations", lambda: _investigations(s))


async def _investigations(s) -> list[dict]:
    stats = await test_stats(s.pool)
    async with s.pool.connection() as c:
        rows = await (await c.execute("""SELECT ci.doc, ci.psi_accession, p.doc AS psi FROM catalog_investigations ci
                                         LEFT JOIN psi_investigations p ON p.accession = ci.psi_accession ORDER BY ci.id""")).fetchall()
    out = []
    for r in rows:
        d, p, st = dict(r["doc"]), r["psi"] or {}, stats.get(r["psi_accession"] or "")
        d["doi"] = p.get("doi") or None
        d["psiUrl"] = p.get("url") or None
        d["dataSizeGB"] = round(p["totalFileSize"] / 1e9, 2) if p.get("totalFileSize") else None
        d["testCount"] = st["n"] if st else 0
        d["rangesSource"] = "curated"
        if st:   # measured envelopes from NASA's own test matrices replace the curated estimates
            if st["o2_min"] is not None:
                d["o2Range"] = [round(st["o2_min"], 2), round(st["o2_max"], 2)]
            if st["p_min"] is not None:
                d["pressureRangePsi"] = [psi(st["p_min"]), psi(st["p_max"])]
            if st["flow_min"] is not None:
                d["flowRangeCms"] = [round(st["flow_min"], 2), round(st["flow_max"], 2)]
            if any(st[k] is not None for k in ("o2_min", "p_min", "flow_min")):
                d["rangesSource"] = "measured"
        out.append(d)
    return out


# ------------------------------------------------------------------ 2. tests of one investigation
OUTCOMES = [(re.compile(r"extinction|self-ext\w*\W*:?\s*SE\b|\bextinguish", re.I), "extinguished"),
            (re.compile(r"quench|flow term\w*:?\s*FT\b", re.I), "quenched"),
            (re.compile(r"completion|steady|burned (completely|out)", re.I), "steady")]


def outcome_of(raw: str) -> str | None:
    for rx, label in OUTCOMES:
        if rx.search(raw or ""):
            return label
    return None


def thickness_mm(measures: dict) -> float | None:
    for k, v in (measures or {}).items():
        if isinstance(v, (int, float)) and re.search(r"thick", k, re.I):
            if re.search(r"\(cm\)|;\s*cm\b", k):
                return round(v * 10, 3)
            if re.search(r"\(mm\)|;\s*mm\b", k):
                return round(v, 3)
    return None


def spread_rate(measures: dict) -> tuple[float | None, float | None]:
    """(microgravity, 1-g) flame spread rate in mm/s when the PSI table names it."""
    ug = g1 = None
    for k, v in (measures or {}).items():
        if isinstance(v, (int, float)) and re.search(r"spread rate", k, re.I):
            if k.strip().startswith("1-g"):
                g1 = v
            else:
                ug = v
    return ug, g1


@router.get("/investigations/{inv_id}/tests", summary="One row per test run of an investigation (from NASA PSI test matrices)")
async def tests(req: Request, inv_id: str, limit: int = Query(2000, ge=1, le=5000), offset: int = Query(0, ge=0)):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", inv_id):
        fail(404, f"Unknown investigation '{inv_id}'", "not_found")
    s = svc(req)
    async with s.pool.connection() as c:
        cat = await (await c.execute("SELECT psi_accession FROM catalog_investigations WHERE id = %s", (inv_id,))).fetchone()
        if not cat:
            fail(404, f"Unknown investigation '{inv_id}'", "not_found")
        if not cat["psi_accession"]:
            return []
        rows = await (await c.execute(
            """SELECT accession, table_id, table_label, row_index, fuel, o2_pct, pressure_kpa, flow_cm_s, gravity_g, diluents, conditions, outcome, measures
               FROM test_rows WHERE accession = %s ORDER BY table_id, row_index LIMIT %s OFFSET %s""", (cat["psi_accession"], limit, offset))).fetchall()
    out = []
    for r in rows:
        ug, g1 = spread_rate(r["measures"])
        out.append({
            "testId": f"{r['accession']}-T{r['table_id']}-R{r['row_index'] + 1}", "investigationId": inv_id,
            "o2Pct": r["o2_pct"], "pressurePsi": psi(r["pressure_kpa"]), "pressureKpa": r["pressure_kpa"], "flowCms": r["flow_cm_s"],
            "gravity": "microgravity" if (r["gravity_g"] or 0) < 0.01 else ("normal" if r["gravity_g"] >= 1 else "partial"),
            "fuel": r["fuel"] or None, "thicknessMm": thickness_mm(r["measures"]),
            "outcome": outcome_of(r["outcome"]), "outcomeRaw": r["outcome"] or None,
            "spreadRateMmS": ug, "spreadRate1gMmS": g1,
            "diluents": r["diluents"] or {}, "conditions": r["conditions"] or {}, "measures": r["measures"] or {},
            "table": r["table_label"], "psiAccession": r["accession"],
        })
    return out


# ------------------------------------------------------------------ 3. habitats
@router.get("/habitats", summary="Crew habitats and their design atmospheres")
async def habitats():
    return [{"id": h["id"], "name": h["label"], "o2Pct": h["o2"], "pressurePsi": round(h["pressure"] * KPA_TO_PSI, 1), "pressureKpa": h["pressure"],
             "gravityG": h["gravity"], "ventilationCms": h["flow"], "volume": h["volume"], "examples": h["examples"], "note": h["note"]} for h in HABITATS]


# ------------------------------------------------------------------ 6. auth (bearer token)
class SignupBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)
    role: Role
    name: str = Field("", max_length=100)


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=128)
    role: Role | None = None


def account_error(e: AccountError):
    return JSONResponse({"error": e.message, "code": e.code}, status_code=e.status, headers=NO_STORE)


@router.post("/auth/signup", status_code=201, summary="Create an account with a role; a verification email is sent (no token until verified)")
async def signup(req: Request, body: SignupBody):
    limit(req, "signup", 0.5)
    try:
        out = await req.app.state.accounts.signup(body.email, body.name, body.password, base_url(req), body.role)
    except AccountError as e:
        return account_error(e)
    u = out["user"]
    return JSONResponse({"token": None, "user": {"email": u["email"], "role": u["profile"], "name": u["name"], "verified": False},
                         "verificationRequired": True, "emailDelivery": out["emailDelivery"],
                         "message": "Check your inbox: open the verification link, then log in."}, status_code=201, headers=NO_STORE)


@router.post("/auth/login", summary="Log in; returns a bearer token. 401 wrong credentials, 403 role mismatch or email not verified")
async def login(req: Request, body: LoginBody):
    limit(req, "login")
    accounts = req.app.state.accounts
    try:
        token, u = await accounts.login(body.email, body.password)
    except AccountError as e:
        return account_error(e)
    if body.role and u["profile"] != body.role:
        await accounts.logout(token)
        return JSONResponse({"error": f"This account is registered as {u['profile']}, not {body.role}.", "code": "role_mismatch"}, status_code=403, headers=NO_STORE)
    return JSONResponse({"token": token, "user": public_user(u), "expiresInDays": svc(req).settings.session_days}, headers=NO_STORE)


@router.get("/auth/me", summary="The signed-in account")
async def me(req: Request):
    return JSONResponse({"user": public_user(await current_user(req))}, headers=NO_STORE)


@router.post("/auth/logout", summary="Revoke the bearer token")
async def logout(req: Request):
    h = req.headers.get("authorization", "")
    token = h[7:].strip() if h.lower().startswith("bearer ") else ""
    await req.app.state.accounts.logout(token)
    return JSONResponse({"signedOut": True}, headers=NO_STORE)


class EmailBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = Field(..., max_length=254)


class ResetBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    token: str = Field(..., min_length=10, max_length=200)
    password: str = Field(..., max_length=128)


@router.post("/auth/resend", summary="Send a new verification email (same answer whether or not the account exists)")
async def resend_verification(req: Request, body: EmailBody):
    limit(req, "resend", 0.3)
    out = await req.app.state.accounts.resend(body.email, base_url(req))
    return JSONResponse({"sent": True, "emailDelivery": out["emailDelivery"]}, headers=NO_STORE)


@router.post("/auth/forgot", summary="Email a password-reset link (same answer whether or not the account exists)")
async def forgot_password(req: Request, body: EmailBody):
    limit(req, "forgot", 0.3)
    out = await req.app.state.accounts.forgot(body.email, base_url(req))
    return JSONResponse({"sent": True, "emailDelivery": out["emailDelivery"]}, headers=NO_STORE)


@router.post("/auth/reset", summary="Choose a new password with the emailed link's token; signs the account out everywhere")
async def reset_password(req: Request, body: ResetBody):
    limit(req, "reset", 0.5)
    try:
        out = await req.app.state.accounts.reset_password(body.token, body.password)
    except AccountError as e:
        return account_error(e)
    return JSONResponse({"reset": True, "email": out["email"]}, headers=NO_STORE)


# ------------------------------------------------------------------ 4. chat (RAG) and 5. conversations
class ChatBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question: str = Field(..., min_length=3, max_length=1000)
    conversationId: uuid.UUID | None = None
    role: Role | None = None
    habitat: str | None = Field(None, max_length=100)


def confidence_from_atlas(r: dict) -> str:
    status = str(r.get("status") or "").lower()
    if r.get("answerable") is False or not r.get("sources"):
        return "none"
    return {"supported": "high", "answered": "high", "ok": "high", "grounded": "high", "partial": "medium"}.get(status, "low")


async def answer_with_atlas(req: Request, question: str, hab: str | None) -> dict:
    atlas, cmap = req.app.state.atlas, await curated_of(svc(req).pool)
    body = {"question": question, "k": 5, "check": True}
    if hab and ATLAS_HABITAT.get(hab):
        body["habitat"] = ATLAS_HABITAT[hab]
    r = await atlas.call("POST", "/ask", body=body)
    sources = r.get("sources") or []
    cited = [s for s in sources if s.get("used")] or sources
    numbers = {s.get("label"): i + 1 for i, s in enumerate(cited)}

    async def snippet(s):
        hit = s.get("hit") or (s.get("chunk_ids") or [None])[0]
        if not hit:
            return ""
        try:
            p = await atlas.call("GET", "/passage", params={"id": hit}, cache=True)
            return re.sub(r"\s+", " ", p.get("text") or "")[:300]
        except AtlasError:
            return ""
    snippets = await asyncio.gather(*[snippet(s) for s in cited])
    answer = re.sub(r"\[(S\d{1,2})\]", lambda m: f"[{numbers[m.group(1)]}]" if m.group(1) in numbers else "", r.get("answer") or "").strip()
    return {"answer": answer or "The NASA PSI passages do not answer this question.", "confidence": confidence_from_atlas(r), "source": "flameatlas",
            "citations": [{"n": i + 1, "investigationId": cmap.get(s.get("investigation_id"), s.get("investigation_id")),
                           "title": f"{s.get('acronym') or s.get('investigation_id')} · {Path(s.get('file') or '').name}".strip(" ·"),
                           "snippet": sn, "url": s.get("url") or "", "pages": s.get("pages") or []} for i, (s, sn) in enumerate(zip(cited, snippets))]}


async def answer_locally(req: Request, question: str, hab: str | None) -> dict:
    s, cmap = svc(req), await curated_of(svc(req).pool)
    r = await s.ask(question, habitat=hab, k=6)
    cites = r.get("citations") or []
    if not cites:
        conf = "none"
    elif r.get("grounded") and r["retrieval"]["coverage"] >= 0.6:
        conf = "high"
    elif r.get("grounded"):
        conf = "medium"
    else:
        conf = "low"
    return {"answer": r.get("answer") or "", "confidence": conf, "source": "local",
            "citations": [{"n": c.get("n"), "investigationId": cmap.get(c.get("accession"), c.get("accession")), "title": c.get("title") or c.get("accession"),
                           "snippet": re.sub(r"\s+", " ", c.get("quote") or "")[:300], "url": c.get("url") or "", "pages": [c["page"]] if c.get("page") else []}
                          for c in cites]}


def followups(role: str, hab: str | None, cites: list[dict], catalog: dict) -> list[str]:
    names = [catalog.get(c["investigationId"], c["investigationId"]) for c in cites if c.get("investigationId")]
    first = names[0] if names else None
    hname = next((h["label"] for h in HABITATS if h["id"] == hab), None)
    out = []
    if first:
        out.append(f"What test conditions did {first} use?")
    if hname:
        out.append(f"What does this mean for a {hname.lower()}?")
    out.append({"engineer": "Which design limits for oxygen and ventilation follow from these tests?",
                "student": "Why do flames behave differently in microgravity?"}.get(role, "Which investigations tested the highest oxygen levels?"))
    return out[:3]


@router.post("/chat", summary="Ask the RAG assistant; answers only from indexed NASA data, with citations. Signed in: saved to a conversation")
async def chat(req: Request, body: ChatBody):
    # Signed in (bearer token): role enforced and the exchange is saved. Without a token (the dashboard's demo login)
    # the question is still answered, but nothing is saved and the per-visitor rate limit applies.
    user = await current_user(req, required=False)
    check_role(user, body.role)
    role = user["profile"] if user else (body.role or "researcher")
    ok, retry = req.app.state.limiter.check("chat:" + (str(user["id"]) if user else req.state.rate_key), limit=20)
    if not ok:
        fail(429, f"Too many questions; try again in {retry} s", "rate_limited")
    hab = habitat_id(body.habitat)
    pool = svc(req).pool
    conv_exists = False
    if user and body.conversationId:
        # The dashboard makes its own conversation ids: an unknown id starts a new conversation with that id.
        async with pool.connection() as c:
            owner = await (await c.execute("SELECT user_id FROM conversations WHERE id = %s", (body.conversationId,))).fetchone()
        if owner and owner["user_id"] != user["id"]:
            fail(404, "Conversation not found", "not_found")
        conv_exists = bool(owner)
    result = None
    if req.app.state.atlas.base:
        try:
            result = await answer_with_atlas(req, body.question, hab)
        except AtlasError:
            result = None          # FlameAtlas offline or link changed: answer from the local index instead
    if result is None:
        result = await answer_locally(req, body.question, hab)
    async with pool.connection() as c:
        cat = {r["id"]: r["doc"].get("name") for r in await (await c.execute("SELECT id, doc FROM catalog_investigations")).fetchall()}
    result["followups"] = followups(role, hab, result["citations"], cat)
    conv = body.conversationId or uuid.uuid4()
    if user:
        async with pool.connection() as c, c.transaction():
            if not conv_exists:
                await c.execute("INSERT INTO conversations (id, user_id, title, habitat, role) VALUES (%s, %s, %s, %s, %s)",
                                (conv, user["id"], body.question[:120], body.habitat, role))
            await c.execute("INSERT INTO messages (conversation_id, role, text) VALUES (%s, 'user', %s)", (conv, body.question))
            await c.execute("""INSERT INTO messages (conversation_id, role, text, citations, followups, confidence, source) VALUES (%s, 'assistant', %s, %s, %s, %s, %s)""",
                            (conv, result["answer"], Jsonb(result["citations"]), Jsonb(result["followups"]), result["confidence"], result["source"]))
            await c.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conv,))
    return JSONResponse({"conversationId": str(conv), "answer": result["answer"], "citations": result["citations"], "followups": result["followups"],
                         "confidence": result["confidence"], "source": result["source"], "role": role, "saved": bool(user)}, headers=NO_STORE)


@router.get("/conversations", summary="The signed-in user's conversations, newest first")
async def conversations(req: Request):
    user = await current_user(req)
    async with svc(req).pool.connection() as c:
        rows = await (await c.execute("""SELECT id::text, title, habitat, created_at AS created, updated_at AS updated,
                                                (SELECT count(*)::int FROM messages m WHERE m.conversation_id = c.id) AS messages
                                         FROM conversations c WHERE user_id = %s ORDER BY updated_at DESC LIMIT 200""", (user["id"],))).fetchall()
    return JSONResponse(json.loads(json.dumps(rows, default=str)), headers=NO_STORE)


async def owned(req: Request, conv_id: str) -> tuple[dict, dict]:
    user = await current_user(req)
    try:
        cid = uuid.UUID(conv_id)
    except ValueError:
        fail(404, "Conversation not found", "not_found")
    async with svc(req).pool.connection() as c:
        conv = await (await c.execute("SELECT id::text, title, habitat, role, created_at AS created, updated_at AS updated FROM conversations WHERE id = %s AND user_id = %s",
                                      (cid, user["id"]))).fetchone()
    if not conv:
        fail(404, "Conversation not found", "not_found")
    return user, conv


@router.get("/conversations/{conv_id}", summary="One conversation with its messages")
async def conversation(req: Request, conv_id: str):
    _, conv = await owned(req, conv_id)
    async with svc(req).pool.connection() as c:
        msgs = await (await c.execute("""SELECT role, text, citations, followups, confidence, source, created_at AS ts FROM messages
                                         WHERE conversation_id = %s ORDER BY id""", (conv["id"],))).fetchall()
    return JSONResponse(json.loads(json.dumps({**conv, "messages": msgs}, default=str)), headers=NO_STORE)


@router.delete("/conversations/{conv_id}", summary="Delete a conversation")
async def delete_conversation(req: Request, conv_id: str):
    _, conv = await owned(req, conv_id)
    async with svc(req).pool.connection() as c:
        await c.execute("DELETE FROM conversations WHERE id = %s", (conv["id"],))
    return JSONResponse({"deleted": True, "id": conv["id"]}, headers=NO_STORE)


# ------------------------------------------------------------------ 7. KPIs
def fmt(n) -> str:
    return f"{n:,.0f}" if isinstance(n, (int, float)) else str(n)


@router.get("/kpis", summary="Headline numbers for a role, computed from the database")
async def kpis(req: Request, role: Role = "researcher"):
    check_role(await current_user(req, required=False), role)
    s = svc(req)

    async def load():
        async with s.pool.connection() as c:
            k = await (await c.execute("""SELECT
                (SELECT coalesce(sum((doc->>'totalFileSize')::numeric), 0) FROM psi_investigations) AS bytes,
                (SELECT count(*)::int FROM psi_investigations) AS psi_n,
                (SELECT count(*)::int FROM catalog_investigations) AS catalog_n,
                (SELECT count(*)::int FROM psi_test_points) AS points,
                (SELECT count(*)::int FROM test_rows) AS rows,
                (SELECT count(*)::int FROM test_rows WHERE o2_pct >= 30) AS rows_o2_30,
                (SELECT max(o2_pct) FROM test_rows) AS o2_max,
                (SELECT count(*)::int FROM doc_chunks) AS passages,
                (SELECT count(*)::int FROM models WHERE active) AS models,
                (SELECT count(DISTINCT doc->>'platform')::int FROM catalog_investigations) AS platforms,
                (SELECT min((doc->'years'->>0)::int) FROM catalog_investigations) AS y0,
                (SELECT max((doc->'years'->>1)::int) FROM catalog_investigations) AS y1,
                (SELECT count(DISTINCT lower(trim(f)))::int FROM catalog_investigations, regexp_split_to_table(doc->>'fuelDetail', ',') f) AS fuels""")).fetchone()
        return k
    k = await s.cached("fe:kpis", load)
    tb = float(k["bytes"]) / 1e12
    sets = {
        "researcher": [[f"{tb:.1f} TB", "Combustion data on NASA PSI"], [fmt(k["psi_n"]), "PSI investigations"],
                       [fmt(k["points"]), "Measured test points"], [fmt(k["passages"]), "Searchable passages"]],
        "engineer": [[fmt(k["rows_o2_30"]), "Test runs at 30% O₂ or more"], [f"{k['o2_max']:.0f}%" if k["o2_max"] is not None else "—", "Highest O₂ tested"],
                     [fmt(len(HABITATS)), "Habitats checked"], [fmt(k["models"]), "Trained models"]],
        "student": [[fmt(k["catalog_n"]), "Fire experiments explained"], [f"{k['y0']}–{k['y1']}" if k["y0"] else "—", "Years of experiments"],
                    [fmt(k["platforms"]), "Spacecraft and labs"], [fmt(k["fuels"]), "Fuels and materials burned"]],
    }
    return {"role": role, "kpis": sets[role]}
