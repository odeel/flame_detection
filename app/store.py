"""
Database operations for the FlameAtlas data: PSI records, normalized test rows, documents and passages.

Generations (in the shared `meta` table) drive cache invalidation:
  data_generation  bumped when PSI records change (shared with the Node backend)
  doc_generation   bumped when documents / passages change
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from psycopg.types.json import Jsonb

from .config import REPO_ROOT
from .db import bump
from .extract.pdf import chunk_pages, clean
from .extract.test_rows import extract_rows

log = logging.getLogger("fif.store")
SNAPSHOT = REPO_ROOT / "assets" / "data" / "psi-snapshot.js"


def load_snapshot(path: Path = SNAPSHOT) -> dict:
    """The committed NASA PSI snapshot is a JS file (`var PSI = {...};`); the JSON object is extracted as is."""
    js = path.read_text(encoding="utf-8")
    start = js.index("var PSI = ") + len("var PSI = ")
    end = js.rindex(";\n  if (typeof module")
    return json.loads(js[start:end])


async def get_meta(conn, key: str, default: str = "") -> str:
    r = await (await conn.execute("SELECT value FROM meta WHERE key = %s", (key,))).fetchone()
    return r["value"] if r else default


async def set_meta(conn, key: str, value) -> None:
    await conn.execute("INSERT INTO meta (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()", (key, str(value)))


async def generations(pool) -> dict:
    async with pool.connection() as c:
        rows = await (await c.execute("SELECT key, value FROM meta WHERE key IN ('data_generation', 'model_generation', 'doc_generation')")).fetchall()
    m = {r["key"]: r["value"] for r in rows}
    return {"data": m.get("data_generation", "0"), "docs": m.get("doc_generation", "0"), "models": m.get("model_generation", "0")}


# ---------------------------------------------------------------- PSI records
async def replace_psi(pool, snapshot: dict) -> dict:
    """Same semantics as the Node backend's replacePsi: one transaction, stable table ids."""
    now = snapshot.get("fetchedAt")
    points = 0
    async with pool.connection() as c, c.transaction():
        await c.execute("TRUNCATE test_rows, psi_test_points, psi_tables, psi_investigations RESTART IDENTITY")
        for p in snapshot["investigations"]:
            tables = p.get("tables") or []
            doc = {k: v for k, v in p.items() if k != "tables"}
            await c.execute(
                """INSERT INTO psi_investigations (accession, acronym, title, project_type, platform, release_date, total_bytes, file_count, doc, fetched_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, coalesce(%s::timestamptz, now()))""",
                (p["accession"], p.get("acronym") or "", p.get("title") or p["accession"], p.get("projectType") or "", p.get("platform") or "",
                 p.get("releaseDate") or "", p.get("totalFileSize") or 0, p.get("fileCount") or 0, Jsonb(doc), now))
            for t in tables:
                tid = (await (await c.execute("INSERT INTO psi_tables (accession, label, file, columns, row_count) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                              (p["accession"], t["label"], t["file"], Jsonb(t["columns"]), len(t["rows"])))).fetchone())["id"]
                if t["rows"]:
                    await c.execute("""INSERT INTO psi_test_points (table_id, row_index, cells)
                                       SELECT %s, (e.ord - 1)::integer, e.value FROM jsonb_array_elements(%s::jsonb) WITH ORDINALITY AS e(value, ord)""",
                                    (tid, json.dumps(t["rows"])))
                points += len(t["rows"])
        for k, v in [("psi_fetched_at", now or ""), ("psi_source", snapshot.get("source", "NASA PSI")),
                     ("psi_research_area", snapshot.get("researchArea", "combustion science")), ("psi_license", snapshot.get("license", "CC0-1.0"))]:
            await set_meta(c, k, v)
        gen = await bump(c, "data_generation")
    return {"investigations": len(snapshot["investigations"]), "points": points, "generation": gen}


async def psi_counts(pool) -> dict:
    async with pool.connection() as c:
        return await (await c.execute(
            """SELECT (SELECT count(*) FROM psi_investigations)::int AS investigations, (SELECT count(*) FROM psi_tables)::int AS tables,
                      (SELECT count(*) FROM psi_test_points)::int AS points, (SELECT count(*) FROM test_rows)::int AS test_rows,
                      (SELECT count(*) FROM documents WHERE kind = 'pdf')::int AS pdf_documents, (SELECT count(*) FROM doc_chunks)::int AS passages,
                      (SELECT coalesce(sum(pages), 0) FROM documents WHERE kind = 'pdf')::int AS pdf_pages,
                      (SELECT count(*) FROM summaries)::int AS summaries""")).fetchone()


async def investigations(pool) -> list[dict]:
    async with pool.connection() as c:
        return await (await c.execute("SELECT accession, acronym, title, platform, doc FROM psi_investigations ORDER BY accession_num")).fetchall()


# ---------------------------------------------------------------- test rows
async def rebuild_test_rows(pool) -> int:
    """Re-extract normalized test rows from every stored PSI table (idempotent)."""
    n = 0
    async with pool.connection() as c, c.transaction():
        await c.execute("TRUNCATE test_rows RESTART IDENTITY")
        tables = await (await c.execute("SELECT t.id, t.accession, t.label, t.columns, i.platform FROM psi_tables t JOIN psi_investigations i USING (accession) ORDER BY t.id")).fetchall()
        for t in tables:
            cells = [r["cells"] for r in await (await c.execute("SELECT cells FROM psi_test_points WHERE table_id = %s ORDER BY row_index", (t["id"],))).fetchall()]
            gravity = 0.0  # every PSI combustion test matrix comes from orbit (ISS, Cygnus) or drop facilities
            rows = extract_rows(t["columns"], cells)
            if not rows:
                continue
            async with c.cursor() as cur:
                await cur.executemany(
                    """INSERT INTO test_rows (accession, table_id, table_label, row_index, fuel, o2_pct, pressure_kpa, flow_cm_s, gravity_g, diluents, conditions, outcome, measures)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [(t["accession"], t["id"], t["label"], r["row_index"], r["fuel"], r["o2_pct"], r["pressure_kpa"], r["flow_cm_s"], gravity,
                      Jsonb(r["diluents"]), Jsonb(r["conditions"]), r["outcome"], Jsonb(r["measures"])) for r in rows])
            n += len(rows)
        await set_meta(c, "test_rows_data_generation", await get_meta(c, "data_generation", "0"))
    return n


async def test_stats(pool) -> dict[str, dict]:
    """Per-investigation test envelope from the normalized rows."""
    async with pool.connection() as c:
        rows = await (await c.execute(
            """SELECT accession, count(*)::int AS n, min(o2_pct) AS o2_min, max(o2_pct) AS o2_max, min(pressure_kpa) AS p_min, max(pressure_kpa) AS p_max,
                      min(flow_cm_s) AS flow_min, max(flow_cm_s) AS flow_max, count(o2_pct)::int AS n_o2,
                      (array_agg(DISTINCT nullif(fuel, '')))[1:8] AS fuels
               FROM test_rows GROUP BY accession""")).fetchall()
    return {r["accession"]: r for r in rows}


# ---------------------------------------------------------------- documents and passages
SECTIONS = [("objectives", "Objectives"), ("hypothesis", "Hypothesis"), ("approach", "Approach"), ("earthBenefits", "Research impacts and Earth benefits")]


def _split(text: str) -> list[str]:
    return [c["text"] for c in chunk_pages([text])] or ([clean(text)] if len(clean(text)) > 40 else [])


async def rebuild_metadata_documents(pool) -> int:
    """One 'metadata' document per investigation, built from official PSI fields and the measured test envelope."""
    stats = await test_stats(pool)
    invs = await investigations(pool)
    n = 0
    async with pool.connection() as c, c.transaction():
        await c.execute("DELETE FROM documents WHERE kind = 'metadata'")
        for inv in invs:
            d, acc = inv["doc"], inv["accession"]
            name = inv["acronym"] or acc
            doc_id = f"{acc}/metadata"
            await c.execute("""INSERT INTO documents (id, accession, title, kind, category, source_url) VALUES (%s, %s, %s, 'metadata', 'PSI record', %s)""",
                            (doc_id, acc, f"{name}: {inv['title']}", f"https://psi.nasa.gov/physci/repo/data/investigations/{acc}"))
            chunks = []
            head = f"{name} ({acc}), {inv['title']}. Platform: {inv['platform'] or d.get('platform', '')}. Hardware: {d.get('hardware', '')}. " \
                   f"Period: {d.get('startDate', '')} to {d.get('endDate', '')}. DOI: {d.get('doi', '')}."
            chunks.append(("Overview", head))
            for key, label in SECTIONS:
                for piece in _split(d.get(key) or ""):
                    chunks.append((label, piece))
            pubs = [p.get("title", "") for p in d.get("publications") or [] if p.get("title")]
            if pubs:
                chunks.append(("Publications", f"{name} publications: " + "; ".join(pubs[:12]) + "."))
            s = stats.get(acc)
            if s:
                parts = [f"The {name} PSI test matrix has {s['n']} normalized test points"]
                if s["o2_min"] is not None:
                    parts.append(f"oxygen from {s['o2_min']:g}% to {s['o2_max']:g}% by volume")
                if s["p_min"] is not None:
                    parts.append(f"pressure from {s['p_min']:g} to {s['p_max']:g} kPa")
                if s["flow_min"] is not None:
                    parts.append(f"flow from {s['flow_min']:g} to {s['flow_max']:g} cm/s")
                fuels = [f for f in (s["fuels"] or []) if f]
                if fuels:
                    parts.append("fuels and materials including " + ", ".join(fuels[:6]))
                chunks.append(("Test matrix", ", ".join(parts) + "."))
            async with c.cursor() as cur:
                await cur.executemany("INSERT INTO doc_chunks (document_id, page, chunk_index, section, text) VALUES (%s, 1, %s, %s, %s)",
                                      [(doc_id, i, sec, txt) for i, (sec, txt) in enumerate(chunks)])
            n += len(chunks)
        await set_meta(c, "metadata_docs_data_generation", await get_meta(c, "data_generation", "0"))
        await bump(c, "doc_generation")
    return n


async def upsert_pdf(pool, *, doc_id: str, accession: str, title: str, category: str, file_name: str, pages: list[str], bytes_: int, sha256: str) -> int:
    chunks = chunk_pages(pages)
    async with pool.connection() as c, c.transaction():
        await c.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        await c.execute("""INSERT INTO documents (id, accession, title, kind, category, file_name, pages, bytes, sha256, source_url)
                           VALUES (%s, %s, %s, 'pdf', %s, %s, %s, %s, %s, %s)""",
                        (doc_id, accession, title, category, file_name, len(pages), bytes_, sha256, f"https://psi.nasa.gov/physci/repo/data/investigations/{accession}"))
        async with c.cursor() as cur:
            await cur.executemany("INSERT INTO doc_chunks (document_id, page, chunk_index, text) VALUES (%s, %s, %s, %s)",
                                  [(doc_id, ch["page"], i, ch["text"]) for i, ch in enumerate(chunks)])
        await bump(c, "doc_generation")
    return len(chunks)


async def documents(pool, accession: str | None = None) -> list[dict]:
    sql = """SELECT d.id, d.accession, d.title, d.kind, d.category, d.file_name AS "fileName", d.pages, d.bytes, d.sha256, d.source_url AS "sourceUrl",
                    d.parsed_at AS "parsedAt", count(c.id)::int AS passages
             FROM documents d LEFT JOIN doc_chunks c ON c.document_id = d.id""" + (" WHERE d.accession = %s" if accession else "") + \
          " GROUP BY d.id ORDER BY substring(d.accession FROM 5)::int, d.kind DESC, d.id"
    async with pool.connection() as c:
        return await (await c.execute(sql, (accession,) if accession else None)).fetchall()


def slug(s: str) -> str:
    return re.sub(r"[^\w.-]+", "_", s).strip("_")
