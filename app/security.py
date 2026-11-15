"""
Authentication and rate limiting.

  * API keys: the same `api_keys` table and SHA-256 hashing as the Node backend, so keys created with
    `npm run apikey` work here too. Send `Authorization: Bearer fif_...` or `X-API-Key: fif_...`.
  * FIF_ADMIN_TOKEN: operator token for admin routes (constant-time comparison).
    Without a token configured, admin routes are allowed from localhost only.
  * Rate limit: sliding one-minute window per API key, or per client IP (in-memory, per process).
"""
from __future__ import annotations

import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def presented_key(req: Request) -> str:
    h = req.headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return req.headers.get("x-api-key", "").strip()


class Auth:
    def __init__(self, services, accounts=None):
        self.s = services
        self.accounts = accounts          # user sessions (bearer tokens from POST /api/auth/login)
        self.cache: dict[str, tuple[float, dict | None]] = {}

    async def principal(self, req: Request) -> dict:
        key = presented_key(req)
        token = self.s.settings.admin_token
        if not key:
            return {"role": "anonymous"}
        if token and hmac.compare_digest(key.encode(), token.encode()):
            return {"role": "admin", "name": "operator"}
        h = hashlib.sha256(key.encode()).hexdigest()
        hit = self.cache.get(h)
        if hit and hit[0] > time.time():
            row = hit[1]
        else:
            async with self.s.pool.connection() as c:
                row = await (await c.execute("SELECT id, name, role FROM api_keys WHERE key_hash = %s AND revoked_at IS NULL", (h,))).fetchone()
                if row:
                    await c.execute("UPDATE api_keys SET last_used_at = now() WHERE id = %s", (row["id"],))
            self.cache[h] = (time.time() + 60, row)
        if row:
            return {"role": row["role"], "name": row["name"], "keyId": row["id"]}
        # Not an API key: maybe a signed-in user's session token (not cached, so sign-out takes effect at once).
        user = await self.accounts.session_user(key) if self.accounts else None
        if user:
            return {"role": "user", "name": user["email"], "user": user}
        raise HTTPException(401, "Invalid or expired token: sign in again")

    async def require_admin(self, req: Request) -> dict:
        p = await self.principal(req)
        if p["role"] == "admin":
            return p
        if not self.s.settings.admin_token and (req.client.host if req.client else "") in LOOPBACK:
            return {"role": "admin", "name": "localhost"}
        raise HTTPException(403 if p["role"] != "anonymous" else 401, "Admin access required (FIF_ADMIN_TOKEN or an admin API key)")


class RateLimiter:
    def __init__(self, per_minute: int):
        self.limit = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, cost: int = 1, limit: int | None = None) -> tuple[bool, int]:
        lim = limit or self.limit
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) + cost > lim:
            return False, max(1, int(60 - (now - q[0])) + 1)
        for _ in range(cost):
            q.append(now)
        if len(self.hits) > 50000:  # bound memory under many distinct clients
            for k in [k for k, v in self.hits.items() if not v][:10000]:
                del self.hits[k]
        return True, 0
