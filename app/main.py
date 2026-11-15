"""
Flame in Freefall: FastAPI backend (FlameAtlas plan, NASA Space Apps 2026 challenge "Flame in Freefall").

  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4      (run from backend-fastapi/)

  /docs                 Swagger UI (OpenAPI 3.1, generated from the route and Pydantic schemas)
  /api/v1/openapi.json  the frozen API schema (a copy is committed as openapi.json; tests check it)
  /api/v1/...           habitats · investigations · rank · tests · ask · brief · summaries · documents · admin

Cross-cutting: request ids, JSON error envelope {error, message}, rate limiting, security headers,
CORS, gzip, ETag + 304 and Cache-Control on GET, API keys shared with the Node backend.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .accounts import Accounts, Mailer
from .atlas import AtlasClient
from .config import REPO_ROOT, get_settings
from .routers import admin, api, atlas, auth, frontend, models
from .security import Auth, RateLimiter
from .services import Services

VERSION = "2.1.0"
log = logging.getLogger("fif")
REQ_ID = re.compile(r"^[\w.-]{8,64}$")
# Same policy the Node server applies to the dashboard (scripts from self, Google Fonts, same-origin API calls).
DASHBOARD_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                 "font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https:; connect-src 'self'; "
                 "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'")
ATLAS_ROOT = {"/habitats", "/investigations", "/compare", "/passage", "/rank", "/ask", "/retrieve", "/predict", "/fuels", "/whatif", "/graph"}
ATLAS_ROOT_PREFIXES = ("/investigation/", "/flammap/", "/gaps/", "/graph/", "/materials/")
PAGES = {"/", "/classic", "/login", "/signup", "/reset", "/verify-email", "/forgot-password", "/reset-password"}  # HTML pages served with the dashboard CSP
CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 409: "conflict", 422: "validation_failed", 429: "rate_limited", 503: "unavailable"}

TAGS = [
    {"name": "system", "description": "Health and liveness"},
    {"name": "auth", "description": "Accounts: sign up, email verification, sign in and sign out (session cookie)"},
    {"name": "habitats", "description": "Crew environments from the challenge brief and their evidence coverage"},
    {"name": "investigations", "description": "NASA PSI combustion investigations and rubric ranking"},
    {"name": "tests", "description": "Normalized ISS test rows extracted from PSI test matrices"},
    {"name": "models", "description": "Models trained on PSI test matrices: cards, version history and predictions"},
    {"name": "ask", "description": "Retrieval-augmented, cited answers from PSI documents"},
    {"name": "briefs", "description": "Printable habitat briefs and pre-generated summaries"},
    {"name": "documents", "description": "Parsed NASA PSI documents and passages"},
    {"name": "frontend", "description": "Routes for the React dashboard (frontend/DATA_CONTRACT.md): catalog, tests, habitats, RAG chat, conversations, role-based accounts, KPIs"},
    {"name": "atlas", "description": "FlameAtlas (team service) on this domain: RAG questions, AHP/OWA habitat ranking, droplet-flame prediction"},
    {"name": "admin", "description": "Document ingestion, summary generation, cache control and jobs"},
]


def create_app(settings=None) -> FastAPI:
    settings = settings or get_settings()
    services = Services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await services.start()
        await frontend.seed_catalog(services.pool)
        yield
        for t in list(app.state.tasks):
            t.cancel()
        await app.state.atlas.close()
        await services.close()

    app = FastAPI(title="Flame in Freefall API (FastAPI)", version=VERSION, lifespan=lifespan, openapi_tags=TAGS,
                  openapi_url="/api/v1/openapi.json", docs_url="/docs", redoc_url="/redoc",
                  description="SI-powered fire-safety insights from NASA Physical Sciences Informatics (PSI) microgravity combustion data: "
                              "habitat rankings, normalized test rows, cited answers from PSI documents and printable briefs.")
    app.state.services = services
    app.state.accounts = Accounts(services, Mailer(settings))
    app.state.auth = Auth(services, app.state.accounts)
    app.state.atlas = AtlasClient(settings)
    app.state.limiter = RateLimiter(settings.rate_limit_per_min)
    app.state.tasks = set()

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    origins = list(dict.fromkeys(settings.cors_list + settings.frontend_origin_list))
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "DELETE"],
                           allow_headers=["Authorization", "X-API-Key", "Content-Type", "If-None-Match", "X-Request-Id"],
                           expose_headers=["ETag", "X-Request-Id"], max_age=600)

    @app.middleware("http")
    async def edge(request: Request, call_next):
        # The React dashboard calls the FlameAtlas routes at the root (/habitats, /rank, /ask...): serve them from
        # this site's /api/v1/atlas/... routes (validated, cached, rate limited).
        p = request.scope["path"]
        if p in ATLAS_ROOT or p.startswith(ATLAS_ROOT_PREFIXES):
            request.scope["path"] = "/api/v1/atlas" + p
            request.scope["raw_path"] = request.scope["path"].encode()
        rid = request.headers.get("x-request-id", "")
        request.state.request_id = rid if REQ_ID.match(rid) else uuid.uuid4().hex
        try:
            request.state.principal = await app.state.auth.principal(request) if request.url.path.startswith("/api/") else {"role": "anonymous"}
        except HTTPException as e:
            if not is_contract(request.url.path):
                return _error(e.status_code, str(e.detail), request.state.request_id)
            # Dashboard routes: an old token must not block /api/auth/login; routes that need an account answer 401 themselves.
            request.state.principal = {"role": "anonymous", "invalidToken": True}
        key = request.headers.get("authorization") or request.headers.get("x-api-key") or ""
        request.state.rate_key = ("k:" + hashlib.sha256(key.encode()).hexdigest()[:16]) if key else ("ip:" + (request.client.host if request.client else "?"))
        if request.url.path.startswith("/api/") and not request.url.path.endswith("/livez"):
            ok, retry = app.state.limiter.check(request.state.rate_key)
            if not ok:
                r = _error(429, "Rate limit exceeded", request.state.request_id, request.url.path)
                r.headers["Retry-After"] = str(retry)
                return r
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path in PAGES or request.url.path.startswith(("/assets/", "/ui-assets/")):
            response.headers.setdefault("Content-Security-Policy", DASHBOARD_CSP)
        elif not request.url.path.startswith(("/docs", "/redoc")):
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'")
        # ETag / 304 for JSON GETs (body already in memory for JSONResponse; streamed responses are skipped).
        if request.method == "GET" and request.url.path.startswith("/api/") and response.status_code == 200 and response.media_type in (None, "application/json") \
                and not isinstance(getattr(response, "body_iterator", None), type(None)):
            body = b"".join([chunk async for chunk in response.body_iterator])
            tag = '"' + hashlib.sha1(body).hexdigest()[:27] + '"'
            headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            headers["ETag"] = tag
            headers.setdefault("cache-control", "public, max-age=30, stale-while-revalidate=300")
            if request.headers.get("if-none-match") == tag:
                return Response(status_code=304, headers={k: v for k, v in headers.items() if k.lower() != "content-type"})
            return Response(content=body, status_code=200, headers=headers, media_type=response.media_type)
        return response

    @app.exception_handler(StarletteHTTPException)  # also covers FastAPI's HTTPException and unknown routes
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = (exc.headers or {}).get("X-Error-Code") if getattr(exc, "headers", None) else None
        return _error(exc.status_code, str(exc.detail), getattr(request.state, "request_id", ""), request.url.path, code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        msg = "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()[:5])
        return _error(422, msg or "invalid request", getattr(request.state, "request_id", ""), request.url.path)

    @app.exception_handler(Exception)
    async def crash(request: Request, exc: Exception):
        log.exception("unhandled error")
        return _error(500, "Internal server error", getattr(request.state, "request_id", ""), request.url.path)

    app.include_router(api.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(models.router, prefix="/api/v1")
    app.include_router(atlas.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(frontend.router)            # /api/... routes of the React dashboard

    # Main UI: the team's React dashboard, built by start.ps1 from its own folder (FIF_FRONTEND_DIR) into ui-dist/, at "/".
    # The classic dashboard (repository root index.html + assets/) stays available at "/classic".
    # Without a React build, "/" falls back to the classic dashboard.
    app.mount("/assets", StaticFiles(directory=REPO_ROOT / "assets"), name="assets")
    ui_dist = REPO_ROOT / "ui-dist"
    if (ui_dist / "ui-assets").is_dir():
        app.mount("/ui-assets", StaticFiles(directory=ui_dist / "ui-assets"), name="ui-assets")
    if (ui_dist / "data").is_dir():
        app.mount("/data", StaticFiles(directory=ui_dist / "data"), name="ui-data")   # the dashboard's own JSON files

    @app.get("/", include_in_schema=False)
    async def root():
        # no-cache: the browser always asks again, so switching dashboards never shows an old saved copy.
        if (ui_dist / "index.html").is_file():
            return FileResponse(ui_dist / "index.html", media_type="text/html", headers={"Cache-Control": "no-cache"})
        return FileResponse(REPO_ROOT / "index.html", media_type="text/html", headers={"Cache-Control": "no-cache"})

    @app.get("/classic", include_in_schema=False)
    async def classic():
        return FileResponse(REPO_ROOT / "index.html", media_type="text/html", headers={"Cache-Control": "no-cache"})

    # Sign-in and sign-up pages (one page, two modes; see assets/js/account.js).
    @app.get("/login", include_in_schema=False)
    @app.get("/signup", include_in_schema=False)
    async def account_page():
        return FileResponse(REPO_ROOT / "account.html", media_type="text/html", headers={"Cache-Control": "no-cache"})

    # Email verification and password-reset pages, in the React dashboard's design (see assets/js/auth-app.js).
    # /reset is kept so reset links sent before this change still open.
    @app.get("/verify-email", include_in_schema=False)
    @app.get("/forgot-password", include_in_schema=False)
    @app.get("/reset-password", include_in_schema=False)
    @app.get("/reset", include_in_schema=False)
    async def auth_app_page():
        return FileResponse(REPO_ROOT / "auth-app.html", media_type="text/html", headers={"Cache-Control": "no-cache"})

    @app.get("/api", include_in_schema=False)
    async def api_info():
        return {"name": "Flame in Freefall API", "docs": "/docs", "openapi": "/api/v1/openapi.json", "version": VERSION}

    return app


def is_contract(path: str) -> bool:
    """Routes of the React dashboard (/api/..., not /api/v1/...), whose contract asks for {\"error\": \"message\"}."""
    return path.startswith("/api/") and not path.startswith("/api/v1/")


def _error(code: int, message: str, rid: str, path: str = "", err_code: str | None = None) -> JSONResponse:
    name = err_code or CODES.get(code, "internal_error" if code >= 500 else "bad_request")
    body = {"error": message, "code": name} if is_contract(path) else {"error": name, "message": message}
    if path.startswith("/api/v1/atlas"):
        body["detail"] = message      # FlameAtlas clients (the React dashboard) read the message from "detail"
    r = JSONResponse(body, status_code=code)
    if rid:
        r.headers["X-Request-Id"] = rid
    return r


app = create_app()
