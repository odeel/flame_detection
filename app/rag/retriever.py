"""
Hybrid passage retrieval over doc_chunks (NASA PSI reports + PSI metadata records).

  1. BM25 (k1 = 1.2, b = 0.75) in memory, with fire-safety synonym expansion (expanded terms weigh 0.4)
  2. PostgreSQL full-text search (ts_rank_cd over the stored tsvector)
  3. Reciprocal-rank fusion of the two lists (k = 60), optional boost for investigations relevant
     to a habitat, and diversity: at most `per_doc` passages from one document.

The in-memory index is rebuilt only when the document generation changes.
"""
from __future__ import annotations

import asyncio
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..text import SYN_INDEX, bibliography_score, tokenize

K1, B, RRF_K, EXPANSION_WEIGHT = 1.2, 0.75, 60, 0.4


@dataclass
class Passage:
    id: int
    document_id: str
    accession: str
    title: str
    kind: str
    category: str
    page: int
    section: str
    text: str
    score: float = 0.0
    signals: dict = field(default_factory=dict)

    def citation(self) -> dict:
        return {"documentId": self.document_id, "accession": self.accession, "title": self.title, "kind": self.kind,
                "category": self.category, "page": self.page if self.kind == "pdf" else None, "section": self.section or None,
                "url": f"https://psi.nasa.gov/physci/repo/data/investigations/{self.accession}"}


class Retriever:
    def __init__(self):
        self.generation = None
        self.passages: list[Passage] = []
        self.tf: list[Counter] = []
        self.lengths: list[int] = []
        self.df: Counter = Counter()
        self.avgdl = 1.0
        self.by_id: dict[int, int] = {}
        self.biblio: list[float] = []
        self._lock = asyncio.Lock()

    async def ensure(self, pool, generation: str):
        if self.generation == generation:
            return
        async with self._lock:
            if self.generation == generation:
                return
            async with pool.connection() as c:
                rows = await (await c.execute(
                    """SELECT c.id, c.document_id, d.accession, d.title, d.kind, d.category, c.page, c.section, c.text
                       FROM doc_chunks c JOIN documents d ON d.id = c.document_id ORDER BY c.id""")).fetchall()
            self._build([Passage(**r) for r in rows])
            self.generation = generation

    def _build(self, passages: list[Passage]):
        self.passages = passages
        self.tf, self.lengths, self.df = [], [], Counter()
        for p in passages:
            toks = tokenize(p.section + " " + p.text)
            c = Counter(toks)
            self.tf.append(c)
            self.lengths.append(len(toks))
            self.df.update(c.keys())
        self.avgdl = sum(self.lengths) / max(1, len(self.lengths))
        self.by_id = {p.id: i for i, p in enumerate(passages)}
        # Reference lists match many technical terms but answer nothing: they are down-weighted at search time.
        self.biblio = [bibliography_score(p.text) for p in passages]

    def idf(self, t: str) -> float:
        n, df = len(self.passages), self.df.get(t, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def query_terms(self, query: str) -> dict[str, float]:
        terms: dict[str, float] = {}
        for t in tokenize(query):
            terms[t] = 1.0
        for t in list(terms):
            for s in SYN_INDEX.get(t, []):
                terms.setdefault(s, EXPANSION_WEIGHT)
        return terms

    def bm25(self, query: str, allowed=None, limit: int = 60) -> list[tuple[int, float]]:
        terms = self.query_terms(query)
        scores = []
        for i, tf in enumerate(self.tf):
            if allowed is not None and self.passages[i].accession not in allowed:
                continue
            s = 0.0
            dl = self.lengths[i] or 1
            for t, w in terms.items():
                f = tf.get(t)
                if f:
                    s += w * self.idf(t) * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avgdl))
            if s > 0:
                scores.append((i, s))
        scores.sort(key=lambda x: -x[1])
        return scores[:limit]

    async def fulltext(self, pool, query: str, accessions=None, limit: int = 60) -> list[tuple[int, float]]:
        words = [w for w in tokenize(query)][:20]
        if not words:
            return []
        tsq = " | ".join(f"{w}:*" for w in words if w.isalnum())
        if not tsq:
            return []
        sql = """SELECT c.id, ts_rank_cd(c.search, q) AS r FROM doc_chunks c JOIN documents d ON d.id = c.document_id,
                 to_tsquery('english', %s) q WHERE c.search @@ q""" + (" AND d.accession = ANY(%s)" if accessions else "") + " ORDER BY r DESC LIMIT %s"
        params = (tsq, list(accessions), limit) if accessions else (tsq, limit)
        async with pool.connection() as c:
            rows = await (await c.execute(sql, params)).fetchall()
        return [(self.by_id[r["id"]], float(r["r"])) for r in rows if r["id"] in self.by_id]

    async def search(self, pool, query: str, k: int = 8, accessions=None, boost: dict | None = None, per_doc: int = 2) -> list[Passage]:
        allowed = set(accessions) if accessions else None
        lex = self.bm25(query, allowed)
        fts = await self.fulltext(pool, query, allowed)
        fused: dict[int, float] = defaultdict(float)
        signals: dict[int, dict] = defaultdict(dict)
        for rank, (i, s) in enumerate(lex):
            fused[i] += 1 / (RRF_K + rank + 1)
            signals[i]["bm25"] = round(s, 3)
        for rank, (i, s) in enumerate(fts):
            fused[i] += 1 / (RRF_K + rank + 1)
            signals[i]["fulltext"] = round(s, 4)
        for i in fused:
            if self.biblio[i] >= 0.3:
                fused[i] *= 0.25
        if boost:
            for i in fused:
                fused[i] *= 1 + 0.5 * boost.get(self.passages[i].accession, 0.0)
        ranked = sorted(fused.items(), key=lambda x: -x[1])
        out, per = [], Counter()
        for i, s in ranked:
            p = self.passages[i]
            if per[p.document_id] >= per_doc:
                continue
            per[p.document_id] += 1
            out.append(Passage(**{**p.__dict__, "score": round(s * 1000, 3), "signals": signals[i]}))
            if len(out) >= k:
                break
        return out

    def coverage(self, query: str, passages: list[Passage]) -> float:
        """Share of the question's content terms that appear in the retrieved passages (0..1)."""
        q = set(tokenize(query))
        if not q:
            return 0.0
        seen = set()
        for p in passages:
            seen |= set(tokenize(p.section + " " + p.text)) & q
        return len(seen) / len(q)
