"""
Client for the FlameAtlas API (the team's RAG question answering, AHP/OWA ranking and droplet-flame prediction).

FlameAtlas runs as its own service (FLAMEATLAS_URL, e.g. an ngrok tunnel). This app serves its routes on
its own domain under /api/v1/atlas/... (see routers/atlas.py), so browsers only ever talk to this site:

  * one base URL in one setting; no CORS, no ngrok warning page, no mixed content for visitors
  * inputs are validated here before anything is forwarded
  * GET results and deterministic POSTs (rank, predict, retrieve) are cached for 10 minutes
  * clear errors: not configured (503), unreachable (503), address serving a web page instead of the API (502),
    and FlameAtlas's own 404 / 422 messages passed through in this API's {error, message} envelope
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import OrderedDict

import httpx

CACHE_TTL = 600.0


def fill_blanks(data, depth: int = 0):
    """Investigation records with no platform or acronym (NASA PSI has none for analysis-only projects such as
    PSI-60, PSI-62, PSI-117) get "Not Applicable" (FlameAtlas's own label) and their PSI id, so clients that format these fields never
    meet null. Nothing else is changed."""
    if depth > 4:
        return data
    if isinstance(data, list):
        return [fill_blanks(x, depth + 1) for x in data]
    if isinstance(data, dict):
        if str(data.get("id", "")).startswith("PSI-"):
            if "platform" in data and not data["platform"]:
                data["platform"] = "Not Applicable"   # FlameAtlas's own wording for these projects
            if "acronym" in data and not data["acronym"]:
                data["acronym"] = data["id"]
        for k in ("results", "items", "experiments"):
            if isinstance(data.get(k), list):
                data[k] = fill_blanks(data[k], depth + 1)
    return data


class AtlasError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class AtlasClient:
    def __init__(self, settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport          # tests inject httpx.MockTransport
        self._client: httpx.AsyncClient | None = None
        self._cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self.hits = self.misses = 0

    @property
    def base(self) -> str:
        return self.settings.atlas_url

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base, transport=self.transport, timeout=httpx.Timeout(self.settings.atlas_timeout, connect=10.0),
                follow_redirects=False,
                # ngrok's free tier shows an HTML warning page to browsers unless this header is sent.
                headers={"Accept": "application/json", "ngrok-skip-browser-warning": "1", "User-Agent": "flame-in-freefall-api"})
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def clear(self) -> int:
        n = len(self._cache)
        self._cache.clear()
        return n

    async def call(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None, cache: bool = False,
                   files: dict | None = None, html: bool = False):
        """files: multipart upload ({field: (name, bytes, type)}). html: the answer is a web page (returned as text)."""
        if not self.base:
            raise AtlasError(503, "FlameAtlas is not connected. Set FLAMEATLAS_URL in backend-fastapi/.env to the FlameAtlas API address and restart.")
        key = None
        if cache:
            key = hashlib.sha256(json.dumps([method, path, params, body], sort_keys=True, default=str).encode()).hexdigest()
            hit = self._cache.get(key)
            if hit and hit[0] > time.time():
                self._cache.move_to_end(key)
                self.hits += 1
                return hit[1]
            self.misses += 1
        for attempt in (1, 2):
            try:
                r = await self._send(method, path, params, body, files, html)
                break
            except httpx.ConnectError as e:
                if attempt == 2:                               # tunnels (ngrok) drop connections for a moment: one retry
                    raise AtlasError(503, f"Cannot reach FlameAtlas at {self.base} ({type(e).__name__}). Is the service and its tunnel running?") from e
                await asyncio.sleep(0.5)
            except httpx.TimeoutException as e:
                raise AtlasError(504, f"FlameAtlas did not answer within {self.settings.atlas_timeout:.0f} s.") from e
            except httpx.HTTPError as e:
                raise AtlasError(503, f"Cannot reach FlameAtlas at {self.base} ({type(e).__name__}). Is the service and its tunnel running?") from e

        ctype = r.headers.get("content-type", "")
        if html and r.status_code == 200 and "html" in ctype:
            if key:
                self._cache[key] = (time.time() + CACHE_TTL, r.text)
            return r.text
        if "json" not in ctype:
            if r.status_code in (301, 302, 303, 307, 308):
                raise AtlasError(502, f"FlameAtlas redirected to {r.headers.get('location', '?')}. Set FLAMEATLAS_URL to the final API address.")
            if "html" in ctype:
                raise AtlasError(502, "The FLAMEATLAS_URL address returned a web page, not the API. It probably points at the Streamlit app: "
                                      "share the FlameAtlas API (its uvicorn port) through ngrok and use that address.")
            raise AtlasError(502, f"FlameAtlas answered with {r.status_code} and content type '{ctype or 'none'}' instead of JSON.")
        try:
            data = r.json()
        except ValueError as e:
            raise AtlasError(502, "FlameAtlas sent invalid JSON.") from e
        if r.status_code >= 400:
            detail = data.get("detail") if isinstance(data, dict) else None
            if isinstance(detail, list):   # FastAPI validation errors
                detail = "; ".join(f"{'.'.join(str(p) for p in d.get('loc', [])[1:])}: {d.get('msg')}" for d in detail[:5])
            status = r.status_code if r.status_code in (400, 404, 409, 413, 422, 429, 503) else 502
            raise AtlasError(status, f"FlameAtlas: {detail or r.reason_phrase}")
        data = fill_blanks(data)
        if key:
            self._cache[key] = (time.time() + CACHE_TTL, data)
            while len(self._cache) > 300:
                self._cache.popitem(last=False)
        return data

    async def _send(self, method, path, params, body, files, html):
        if files:
            return await self._http().request(method, path, params=params, files=files)
        return await self._http().request(method, path, params=params, json=body, headers={"Accept": "text/html"} if html else None)

    async def status(self) -> dict:
        # The upstream address is not shown: visitors must go through this site's validation and rate limits.
        out = {"configured": bool(self.base), "reachable": False, "cache": {"entries": len(self._cache), "hits": self.hits, "misses": self.misses}}
        if not self.base:
            out["message"] = "Set FLAMEATLAS_URL in backend-fastapi/.env."
            return out
        t0 = time.perf_counter()
        try:
            fuels = await self.call("GET", "/fuels")
            out.update(reachable=True, latencyMs=round((time.perf_counter() - t0) * 1000, 1), fuels=fuels)
        except AtlasError as e:
            out.update(message=e.message)
        return out
