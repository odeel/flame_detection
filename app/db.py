"""PostgreSQL access: async connection pool (psycopg 3) and versioned migrations under an advisory lock."""
from __future__ import annotations

import re
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import BACKEND_DIR, REPO_ROOT

MIGRATION_LOCK = 724519  # same lock id as the Node backend, so the two never migrate at once
MIGRATION_DIRS = [REPO_ROOT / "server" / "db" / "migrations" / "postgres", BACKEND_DIR / "migrations"]


def migration_files() -> list[tuple[int, Path]]:
    out = []
    for d in MIGRATION_DIRS:
        for f in sorted(d.glob("*.sql")):
            m = re.match(r"^(\d+)_.+\.sql$", f.name)
            if m:
                out.append((int(m.group(1)), f))
    return sorted(out)


async def open_pool(url: str, max_size: int = 10) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(url, min_size=1, max_size=max_size, open=False,
                               kwargs={"row_factory": dict_row, "application_name": "flame-in-freefall-fastapi", "autocommit": True,
                                       "options": "-c statement_timeout=30000"})
    await pool.open(wait=True, timeout=10)
    return pool


async def migrate(pool: AsyncConnectionPool) -> list[str]:
    applied = []
    async with pool.connection() as c:
        await c.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        try:
            await c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version integer PRIMARY KEY, name text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
            done = {r["version"] for r in await (await c.execute("SELECT version FROM schema_migrations")).fetchall()}
            for version, path in migration_files():
                if version in done:
                    continue
                async with c.transaction():
                    await c.execute(path.read_text(encoding="utf-8"))
                    await c.execute("INSERT INTO schema_migrations (version, name) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING", (version, path.name))
                applied.append(path.name)
        finally:
            await c.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
    return applied


async def fetchall(pool, sql, params=None):
    async with pool.connection() as c:
        return await (await c.execute(sql, params)).fetchall()


async def fetchone(pool, sql, params=None):
    async with pool.connection() as c:
        return await (await c.execute(sql, params)).fetchone()


async def bump(conn, key: str) -> int:
    """Atomic generation counter (shared with the Node backend); NOTIFY lets every server drop caches."""
    r = await (await conn.execute(
        "INSERT INTO meta (key, value) VALUES (%s, '1') ON CONFLICT (key) DO UPDATE SET value = (meta.value::integer + 1)::text, updated_at = now() RETURNING value",
        (key,))).fetchone()
    await conn.execute("SELECT pg_notify('fif_generation', %s)", (f"{key}={r['value']}",))
    return int(r["value"])
