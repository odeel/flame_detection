"""
Service layer: everything the routes call. Nothing here knows about HTTP.

Caching
  * Results are memoized in an in-process LRU keyed by the data + document generations, so they are
    dropped as soon as PSI data, test rows or documents change (on this or another server).
  * Derived tables (test_rows, metadata passages, summaries, briefs) are rebuilt at startup and after
    ingestion when their stored generation no longer matches meta.data_generation / doc_generation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from collections import OrderedDict, defaultdict
from pathlib import Path

from anthropic import AsyncAnthropic

from . import brief as brief_mod
from . import ml, ranking, store, summaries
from .config import REPO_ROOT, Settings
from .db import bump, migrate, open_pool
from .extract.pdf import PdfError, extract_pages, pdftotext_available, title_from_file
from .habitats import BY_ID, HABITATS
from .psi_client import PsiClient, read_manifest, sha256_file, write_manifest
from .rag import answer as answer_mod
from .rag.retriever import Retriever

log = logging.getLogger("fif.services")


# Chemical names and formulas used interchangeably in PSI tables ("ethylene" vs "C2H4").
FUEL_ALIASES = [("ethylene", "c2h4"), ("methane", "ch4"), ("ethane", "c2h6"), ("propane", "c3h8"), ("propylene", "c3h6"), ("butane", "c4h10"),
                ("hydrogen", "h2"), ("dodecane", "c12h26"), ("heptane", "c7h16"), ("pmma", "acrylic"), ("sibal", "cotton-fiberglass")]


def fuel_aliases(fuel: str) -> list[str]:
    f = fuel.lower().strip()
    out = [f]
    for a, b in FUEL_ALIASES:
        if f == a:
            out.append(b)
        elif f == b:
            out.append(a)
    return out


class LRU:
    def __init__(self, max_items: int = 500):
        self.max, self.data, self.hits, self.misses = max_items, OrderedDict(), 0, 0

    def get(self, key):
        if key in self.data:
            self.data.move_to_end(key)
            self.hits += 1
            return self.data[key]
        self.misses += 1
        return None

    def set(self, key, value):
        self.data[key] = value
        self.data.move_to_end(key)
        while len(self.data) > self.max:
            self.data.popitem(last=False)

    def clear(self) -> int:
        n = len(self.data)
        self.data.clear()
        return n

    def stats(self) -> dict:
        return {"entries": len(self.data), "hits": self.hits, "misses": self.misses}


class Services:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pool = None
        self.cache = LRU()
        self.retriever = Retriever()
        self.claude = AsyncAnthropic() if settings.anthropic_api_key else None
        self.started = time.time()
        self._gen = None
        self._gen_at = 0.0

    # ------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self.pool = await open_pool(self.settings.database_url, self.settings.pool_max)
        applied = await migrate(self.pool)
        if applied:
            log.info("applied migrations: %s", ", ".join(applied))
        if self.settings.seed_on_start:
            await self.seed_if_empty()
            await self.seed_models()
            await self.ensure_derived()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def generation(self, max_age: float = 2.0) -> str:
        """Combined data/doc generation; read from the database at most every 2 s."""
        if self._gen and time.time() - self._gen_at < max_age:
            return self._gen
        g = await store.generations(self.pool)
        gen = f"{g['data']}.{g['docs']}"
        if gen != self._gen:
            self.cache.clear()
        self._gen, self._gen_at = gen, time.time()
        return gen

    async def cached(self, key: str, fn):
        k = f"{await self.generation()}|{key}"
        hit = self.cache.get(k)
        if hit is not None:
            return hit
        v = await fn()
        self.cache.set(k, v)
        return v

    async def _locked(self, name: str, fn):
        async with self.pool.connection() as c:
            await c.execute("SELECT pg_advisory_lock(hashtext(%s))", (name,))
            try:
                return await fn()
            finally:
                await c.execute("SELECT pg_advisory_unlock(hashtext(%s))", (name,))

    async def seed_if_empty(self) -> bool:
        async def go():
            if (await store.psi_counts(self.pool))["investigations"]:
                return False
            r = await store.replace_psi(self.pool, store.load_snapshot())
            log.info("seeded PSI snapshot: %s investigations, %s test points", r["investigations"], r["points"])
            return True
        return await self._locked("fif-seed", go)

    async def ensure_derived(self, force: bool = False) -> dict:
        """Rebuild test rows, metadata passages, summaries and briefs if PSI data changed."""
        async def go():
            done = {}
            async with self.pool.connection() as c:
                data_gen = await store.get_meta(c, "data_generation", "0")
                tr = await store.get_meta(c, "test_rows_data_generation", "")
                md = await store.get_meta(c, "metadata_docs_data_generation", "")
                sm = await store.get_meta(c, "summaries_generation", "")
            if force or tr != data_gen:
                done["testRows"] = await store.rebuild_test_rows(self.pool)
            if force or md != data_gen:
                done["metadataPassages"] = await store.rebuild_metadata_documents(self.pool)
            self._gen = None
            gen = await self.generation(0)
            if force or sm != gen or done:
                done["summaries"] = await self.regenerate_summaries()
            return done
        out = await self._locked("fif-py-derived", go)
        if out:
            log.info("derived data rebuilt: %s", out)
        return out

    # ------------------------------------------------------------ ranking
    async def rank_inputs(self):
        async def load():
            invs = await store.investigations(self.pool)
            stats = await store.test_stats(self.pool)
            async with self.pool.connection() as c:
                rows = await (await c.execute("SELECT accession, o2_pct, pressure_kpa FROM test_rows")).fetchall()
                docs = await (await c.execute("SELECT accession, count(*)::int AS n FROM documents WHERE kind = 'pdf' GROUP BY accession")).fetchall()
            by = defaultdict(list)
            for r in rows:
                by[r["accession"]].append(r)
            return invs, stats, dict(by), {d["accession"]: d["n"] for d in docs}
        return await self.cached("rank_inputs", load)

    async def rank(self, habitat: str | None = None, weights: dict | None = None, query: str | None = None, pillar: str | None = None,
                   min_tests: int = 0, limit: int = 50) -> dict:
        h = BY_ID.get(habitat) if habitat else None
        key = f"rank|{habitat}|{sorted((weights or {}).items())}|{query}|{pillar}|{min_tests}"

        async def go():
            invs, stats, rows, docs = await self.rank_inputs()
            return ranking.rank(invs, h, stats, rows, docs, weights, query, pillar, min_tests)
        r = await self.cached(key, go)
        return {"habitat": h, **r, "total": len(r["items"]), "items": r["items"][:limit]}

    async def habitat_relevance(self, habitat: str) -> dict[str, float]:
        r = await self.rank(habitat, limit=100)
        return {i["accession"]: i["score"] / 100 for i in r["items"]}

    # ------------------------------------------------------------ tests
    async def tests(self, *, fuel=None, o2=None, o2_tol=1.0, o2_min=None, o2_max=None, pressure_min=None, pressure_max=None, flow_min=None,
                    flow_max=None, outcome=None, accession=None, diluent=None, limit=100, offset=0) -> dict:
        where, params = [], []
        if fuel:
            alts = fuel_aliases(fuel)
            where.append("(" + " OR ".join(["lower(t.fuel) LIKE %s"] * len(alts)) + ")")
            params += ["%" + a.replace("%", "").replace("_", "\\_") + "%" for a in alts]
        if o2 is not None:
            where.append("t.o2_pct BETWEEN %s AND %s")
            params += [o2 - o2_tol, o2 + o2_tol]
        for col, lo, hi in (("o2_pct", o2_min, o2_max), ("pressure_kpa", pressure_min, pressure_max), ("flow_cm_s", flow_min, flow_max)):
            if lo is not None:
                where.append(f"t.{col} >= %s")
                params.append(lo)
            if hi is not None:
                where.append(f"t.{col} <= %s")
                params.append(hi)
        if outcome:
            where.append("t.outcome ILIKE %s")
            params.append("%" + outcome.replace("%", "") + "%")
        if accession:
            where.append("t.accession = %s")
            params.append(accession)
        if diluent:
            where.append("t.diluents ? %s")
            params.append(diluent)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        async with self.pool.connection() as c:
            total = (await (await c.execute(f"SELECT count(*)::int AS n FROM test_rows t{w}", params)).fetchone())["n"]
            rows = await (await c.execute(
                f"""SELECT t.id, t.accession, i.acronym, t.table_id AS "tableId", t.table_label AS "table", t.row_index AS "rowIndex", t.fuel,
                           t.o2_pct AS "o2Pct", t.pressure_kpa AS "pressureKpa", t.flow_cm_s AS "flowCmS", t.gravity_g AS "gravityG",
                           t.diluents, t.conditions, t.outcome, t.measures
                    FROM test_rows t JOIN psi_investigations i USING (accession){w}
                    ORDER BY i.accession_num, t.table_id, t.row_index LIMIT %s OFFSET %s""", params + [limit, offset])).fetchall()
        return {"total": total, "offset": offset, "limit": limit, "items": rows}

    async def test_facets(self) -> dict:
        async def go():
            async with self.pool.connection() as c:
                fuels = await (await c.execute("SELECT fuel, count(*)::int AS n FROM test_rows WHERE fuel <> '' GROUP BY fuel ORDER BY n DESC LIMIT 60")).fetchall()
                rng = await (await c.execute("""SELECT count(*)::int AS rows, min(o2_pct) AS o2_min, max(o2_pct) AS o2_max, min(pressure_kpa) AS p_min,
                                               max(pressure_kpa) AS p_max, min(flow_cm_s) AS flow_min, max(flow_cm_s) AS flow_max,
                                               count(o2_pct)::int AS with_o2, count(pressure_kpa)::int AS with_pressure, count(flow_cm_s)::int AS with_flow,
                                               count(nullif(outcome, ''))::int AS with_outcome FROM test_rows""")).fetchone()
                dil = await (await c.execute("SELECT key AS diluent, count(*)::int AS n FROM test_rows, jsonb_object_keys(diluents) AS key GROUP BY key ORDER BY n DESC")).fetchall()
                per = await (await c.execute("""SELECT t.accession, i.acronym, count(*)::int AS rows FROM test_rows t JOIN psi_investigations i USING (accession)
                                               GROUP BY t.accession, i.acronym, i.accession_num ORDER BY i.accession_num""")).fetchall()
            return {"summary": rng, "fuels": fuels, "diluents": dil, "investigations": per}
        return await self.cached("test_facets", go)

    # ------------------------------------------------------------ ask
    async def ask(self, question: str, habitat: str | None = None, accessions: list[str] | None = None, k: int = 6, mode: str = "auto") -> dict:
        await self.retriever.ensure(self.pool, await self.generation())
        boost = await self.habitat_relevance(habitat) if habitat else None
        q = question + (f" {BY_ID[habitat]['label']}" if habitat and habitat in BY_ID else "")
        passages = await self.retriever.search(self.pool, q, k=k, accessions=accessions, boost=boost)
        coverage = self.retriever.coverage(question, passages)
        result = {"question": question, "habitat": habitat, "retrieval": {"method": "hybrid BM25 + PostgreSQL full-text, reciprocal-rank fusion",
                  "passagesSearched": len(self.retriever.passages), "coverage": round(coverage, 3)}}
        if not passages:
            return {**result, "answer": "No NASA PSI passage matches this question.", "generator": "none", "grounded": False, "citations": [],
                    "unverifiedNumbers": [], "passages": []}
        gen, warnings = "extractive-v1", []
        out = None
        if mode in ("auto", "claude") and self.claude:
            try:
                out = await answer_mod.with_claude(self.claude, self.settings.claude_model, question, passages)
                gen = f"claude:{out.get('model') or self.settings.claude_model}"
                if not out["answer"]:
                    out = None
            except Exception as e:  # network, auth or refusal: fall back to the extractive answer
                log.warning("claude answer failed: %s", e)
                warnings.append(f"LLM unavailable ({type(e).__name__}); extractive answer returned instead.")
                out = None
        elif mode == "claude":
            warnings.append("ANTHROPIC_API_KEY is not set; extractive answer returned instead.")
        if out is None:
            out = answer_mod.extractive(question, passages)
            gen = "extractive-v1"
        if not out["answer"]:
            out = {"answer": "The retrieved NASA PSI passages do not directly answer this question. The closest passages are listed below.", "cited": []}
        unverified = answer_mod.number_guard(out["answer"], question, out["cited"] or passages)
        if unverified:
            warnings.append("Some numbers in the answer were not found in the cited passages: " + ", ".join(unverified))
        if coverage < 0.4:
            warnings.append("Low retrieval coverage: the passages match few of the question's terms, so the answer may be partial.")
        return {**result, "answer": out["answer"], "generator": gen, "grounded": not unverified and bool(out["cited"]),
                "citations": [{"n": i + 1, **p.citation(), "quote": p.text[:400]} for i, p in enumerate(out["cited"])],
                "unverifiedNumbers": unverified, "warnings": warnings,
                "passages": [{**p.citation(), "score": p.score, "signals": p.signals, "text": p.text} for p in passages]}

    # ------------------------------------------------------------ briefs and summaries
    async def build_brief(self, habitat: str) -> dict:
        h = BY_ID[habitat]
        ranked = (await self.rank(habitat, limit=100))["items"]
        async with self.pool.connection() as c:
            ev = await (await c.execute(
                """SELECT t.accession, i.acronym, count(*)::int AS n, min(t.o2_pct) AS o2_min, max(t.o2_pct) AS o2_max, min(t.pressure_kpa) AS p_min,
                          max(t.pressure_kpa) AS p_max, (array_agg(DISTINCT nullif(t.fuel, '')))[1:6] AS fuels,
                          (array_agg(DISTINCT nullif(t.outcome, '')))[1:4] AS outcomes
                   FROM test_rows t JOIN psi_investigations i USING (accession)
                   WHERE t.o2_pct BETWEEN %s AND %s AND (t.pressure_kpa IS NULL OR t.pressure_kpa BETWEEN %s AND %s)
                   GROUP BY t.accession, i.acronym ORDER BY n DESC""", (h["o2"] - 3, h["o2"] + 3, h["pressure"] - 20, h["pressure"] + 20))).fetchall()
            enriched = (await (await c.execute("SELECT count(*)::int AS n FROM test_rows WHERE o2_pct >= %s", (h["o2"],))).fetchone())["n"]
        for e in ev:
            e["fuels"] = [f for f in e["fuels"] or [] if f]
            e["outcomes"] = [o for o in e["outcomes"] or [] if o]
        near = sum(e["n"] for e in ev)
        await self.retriever.ensure(self.pool, await self.generation())
        top = {r["accession"]: r["score"] / 100 for r in ranked}
        ps = await self.retriever.search(self.pool, ranking.habitat_query(h), k=4, boost=top, per_doc=1)
        passages = [{**p.citation(), "text": p.text[:500]} for p in ps]
        return brief_mod.build(h, ranked, ev, near, enriched, passages)

    async def regenerate_summaries(self) -> int:
        invs = await store.investigations(self.pool)
        stats = await store.test_stats(self.pool)
        gen = await self.generation(0)
        n = 0
        async with self.pool.connection() as c, c.transaction():
            for inv in invs:
                await summaries.store(c, "investigation", inv["accession"], summaries.EXTRACTIVE, summaries.extractive_summary(inv, stats.get(inv["accession"])), gen)
                n += 1
        self.cache.clear()
        for h in HABITATS:
            b = await self.build_brief(h["id"])
            async with self.pool.connection() as c:
                await summaries.store(c, "brief", h["id"], summaries.EXTRACTIVE, b, gen)
            n += 1
        async with self.pool.connection() as c:
            await store.set_meta(c, "summaries_generation", gen)
        return n

    async def claude_summaries(self, accessions: list[str] | None = None) -> dict:
        """Optional LLM summaries, grounded in each investigation's passages (requires ANTHROPIC_API_KEY)."""
        if not self.claude:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        invs = [i for i in await store.investigations(self.pool) if not accessions or i["accession"] in accessions]
        await self.retriever.ensure(self.pool, await self.generation())
        gen, done, failed = await self.generation(0), 0, []
        for inv in invs:
            name = inv["acronym"] or inv["accession"]
            q = f"Summarize {name}: its objective, what was tested (fuels, oxygen, pressure, flow), the key findings, and what they mean for fire safety in crewed spacecraft and habitats."
            ps = await self.retriever.search(self.pool, q, k=8, accessions=[inv["accession"]], per_doc=4)
            if not ps:
                continue
            try:
                out = await answer_mod.with_claude(self.claude, self.settings.claude_model, q, ps)
            except Exception as e:
                failed.append({"accession": inv["accession"], "error": str(e)[:200]})
                continue
            content = {"accession": inv["accession"], "acronym": name, "summary": out["answer"],
                       "citations": [{"n": i + 1, **p.citation()} for i, p in enumerate(out["cited"])],
                       "unverifiedNumbers": answer_mod.number_guard(out["answer"], q, out["cited"] or ps)}
            async with self.pool.connection() as c:
                await summaries.store(c, "investigation", inv["accession"], f"claude:{out.get('model') or self.settings.claude_model}", content, gen)
            done += 1
        return {"generated": done, "failed": failed}

    # ------------------------------------------------------------ documents
    async def ingest_documents(self, *, accessions=None, categories=None, max_mb: float = 40, limit: int | None = None, log_fn=log.info) -> dict:
        """Download PSI PDFs (resumable), parse them into page passages and store them."""
        if not pdftotext_available():
            raise RuntimeError("pdftotext not found: install poppler-utils")
        root: Path = self.settings.documents_dir
        manifest = read_manifest(root)
        client = PsiClient()
        stats = {"files": 0, "downloaded": 0, "parsed": 0, "passages": 0, "pages": 0, "skipped": 0, "errors": []}
        try:
            invs = [i for i in await store.investigations(self.pool) if not accessions or i["accession"] in accessions]
            async with self.pool.connection() as c:
                known = {r["id"]: r["sha256"] for r in await (await c.execute("SELECT id, sha256 FROM documents WHERE kind = 'pdf'")).fetchall()}
            for inv in invs:
                acc = inv["accession"]
                detail = await client.investigation(acc)
                files = PsiClient.document_files(detail, categories, int(max_mb * 1024 * 1024))
                for f in files:
                    if limit is not None and stats["files"] >= limit:
                        break
                    stats["files"] += 1
                    doc_id = f"{acc}/{f['file_name']}"
                    try:
                        got = await client.download(acc, f, root / acc)
                        stats["downloaded"] += got["downloaded"]
                        manifest["files"][doc_id] = {k: got[k] for k in ("category", "bytes", "version", "s3_version_id", "s3_path", "sha256")} | {"path": str(Path(got["path"]).relative_to(root))}
                        if known.get(doc_id) == got["sha256"]:
                            stats["skipped"] += 1
                            continue
                        pages = await asyncio.to_thread(extract_pages, Path(got["path"]))
                        n = await store.upsert_pdf(self.pool, doc_id=doc_id, accession=acc, title=title_from_file(acc, f["file_name"]), category=f["category"],
                                                   file_name=f["file_name"], pages=pages, bytes_=f["bytes"], sha256=got["sha256"])
                        stats["parsed"] += 1
                        stats["passages"] += n
                        stats["pages"] += len(pages)
                        log_fn(f"  {doc_id}: {len(pages)} pages, {n} passages")
                    except (RuntimeError, PdfError, OSError) as e:
                        stats["errors"].append({"document": doc_id, "error": str(e)[:200]})
                        log_fn(f"  {doc_id}: {e}")
                write_manifest(root, manifest)
        finally:
            await client.close()
        return stats

    async def index_local_documents(self, log_fn=log.info) -> dict:
        """Parse PDFs already on disk (from the manifest) without network access."""
        root: Path = self.settings.documents_dir
        manifest = read_manifest(root)
        stats = {"parsed": 0, "passages": 0, "errors": []}
        for doc_id, m in sorted(manifest["files"].items()):
            path = root / m["path"]
            if not path.exists():
                continue
            acc, file_name = doc_id.split("/", 1)
            try:
                pages = await asyncio.to_thread(extract_pages, path)
                n = await store.upsert_pdf(self.pool, doc_id=doc_id, accession=acc, title=title_from_file(acc, file_name), category=m.get("category", ""),
                                           file_name=file_name, pages=pages, bytes_=path.stat().st_size, sha256=sha256_file(path))
                stats["parsed"] += 1
                stats["passages"] += n
                log_fn(f"  {doc_id}: {len(pages)} pages, {n} passages")
            except PdfError as e:
                stats["errors"].append({"document": doc_id, "error": str(e)})
        return stats

    # ------------------------------------------------------------ trained models
    async def seed_models(self) -> int:
        async def go():
            async with self.pool.connection() as c:
                n = await ml.seed_if_empty(c)
            if n:
                log.info("loaded %s bundled model artifacts into PostgreSQL", n)
            return n
        return await self._locked("fif-seed-models", go)

    async def active_models(self) -> list[dict]:
        async def load():
            async with self.pool.connection() as c:
                return [r["artifact"] for r in await (await c.execute("SELECT artifact FROM models WHERE active ORDER BY id")).fetchall()]
        return await self.cached(f"models|{await self._model_generation()}", load)

    async def active_model(self, model_id: str) -> dict | None:
        return next((a for a in await self.active_models() if a["id"] == model_id), None)

    async def _model_generation(self) -> str:
        async with self.pool.connection() as c:
            return await store.get_meta(c, "model_generation", "0")

    async def model_version(self, model_id: str, version: int) -> dict | None:
        async with self.pool.connection() as c:
            r = await (await c.execute("SELECT artifact FROM models WHERE id = %s AND version = %s", (model_id, version))).fetchone()
        return r["artifact"] if r else None

    async def model_versions(self, model_id: str) -> list[dict]:
        async with self.pool.connection() as c:
            return await (await c.execute(
                """SELECT version, algorithm, primary_metric AS "primaryMetric", score, n, data_hash AS "dataHash",
                          to_char(trained_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') AS "trainedAt", active
                   FROM models WHERE id = %s ORDER BY version DESC""", (model_id,))).fetchall()

    async def predict(self, model_id: str, inputs: list[dict]) -> dict | None:
        art = await self.active_model(model_id)
        if not art:
            return None
        runs = [ml.predict_artifact(art, i) for i in inputs]
        async with self.pool.connection() as c:
            async with c.cursor() as cur:
                await cur.executemany("INSERT INTO predictions (model_id, version, input, output) VALUES (%s, %s, %s, %s)",
                                      [(model_id, art["version"], json.dumps(r["input"]), r["value"]) for r in runs])
        return {"model": model_id, "version": art["version"], "algorithm": art["algorithm"], "results": [ml.format_result(art, r) for r in runs]}

    async def prediction_count(self) -> int:
        async with self.pool.connection() as c:
            return (await (await c.execute("SELECT count(*)::int AS n FROM predictions")).fetchone())["n"]

    async def run_node_script(self, script: str, timeout: float = 900) -> str:
        """Run a Node worker script (training / PSI ingest share their code with the browser) against this database."""
        node = shutil.which("node")
        if not node:
            raise RuntimeError("Node.js 22.13+ is required for training and PSI ingest (it runs assets/js/training.js). Install it and restart.")
        env = {**os.environ, "DATABASE_URL": self.settings.database_url}
        proc = await asyncio.to_thread(subprocess.run, [node, "--disable-warning=ExperimentalWarning", str(REPO_ROOT / "scripts" / script)],
                                       cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError(((proc.stderr or proc.stdout).strip().splitlines() or [f"{script} failed"])[-1][:500])
        self._gen = None
        self.cache.clear()
        return proc.stdout

    async def train_models(self) -> list[dict]:
        await self.run_node_script("train.mjs")
        return [{"id": a["id"], "version": a["version"], "algorithm": a["algorithm"]} for a in await self.active_models()]

    async def ingest_psi(self) -> dict:
        await self.run_node_script("fetch-psi.mjs", timeout=1800)
        await self.ensure_derived()
        counts = await store.psi_counts(self.pool)
        return {"investigations": counts["investigations"], "points": counts["points"],
                "models": [{"id": a["id"], "version": a["version"]} for a in await self.active_models()]}

    # ------------------------------------------------------------ jobs
    async def run_job(self, kind: str, coro_fn):
        async with self.pool.connection() as c:
            try:
                job = (await (await c.execute("INSERT INTO jobs (kind, status) VALUES (%s, 'running') RETURNING id", (kind,))).fetchone())["id"]
            except Exception as e:
                if getattr(e, "sqlstate", "") == "23505":
                    raise JobConflict(f"A {kind} job is already running") from e
                raise
        try:
            detail = await coro_fn()
            status = "succeeded"
        except Exception as e:
            detail, status = {"error": str(e)[:500]}, "failed"
        async with self.pool.connection() as c:
            await c.execute("UPDATE jobs SET status = %s, finished_at = now(), detail = %s WHERE id = %s", (status, json.dumps(detail, default=str), job))
            if status == "succeeded" and kind in ("documents",):
                await bump(c, "doc_generation")
        self._gen = None
        return {"job": job, "status": status, "detail": detail}


class JobConflict(RuntimeError):
    pass
