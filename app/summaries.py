"""
Pre-generated investigation summaries, stored in the `summaries` table so the demo works offline.

  extractive-v1   built from official PSI fields (first sentences of objectives, approach, Earth benefits)
                  plus the measured test envelope. No model involved: every sentence is NASA's own text.
  claude:<model>  optional (scripts/precompute.py --claude): Claude answers a fixed summary question
                  from that investigation's retrieved passages, with API-native citations.
"""
from __future__ import annotations

import re

from psycopg.types.json import Jsonb

from .habitats import PILLAR_OF
from .text import sentences

EXTRACTIVE = "extractive-v1"


def first_sentence(text: str, max_chars: int = 400) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    t = re.sub(r"^(objectives?|the objectives? of (this|the) investigation (was|were) to):?\s*", "", t, flags=re.I)
    ss = sentences(t) or ([t] if t else [])
    s = ss[0] if ss else ""
    return (s[: max_chars - 1] + "…") if len(s) > max_chars else s


def extractive_summary(inv: dict, stats: dict | None) -> dict:
    d, acc = inv["doc"], inv["accession"]
    name = inv["acronym"] or acc
    points = [x for x in (first_sentence(d.get("objectives")), first_sentence(d.get("approach")), first_sentence(d.get("earthBenefits"))) if x]
    env = None
    if stats:
        env = {"testPoints": stats["n"], "o2Pct": [stats["o2_min"], stats["o2_max"]] if stats["o2_min"] is not None else None,
               "pressureKpa": [stats["p_min"], stats["p_max"]] if stats["p_min"] is not None else None,
               "flowCmS": [stats["flow_min"], stats["flow_max"]] if stats["flow_min"] is not None else None,
               "fuels": [f for f in (stats["fuels"] or []) if f][:8]}
    return {
        "accession": acc, "acronym": name, "title": inv["title"],
        "headline": points[0] if points else inv["title"],
        "summary": points,
        "testEnvelope": env,
        "pillars": PILLAR_OF.get(acc, []),
        "platform": inv["platform"] or d.get("platform", ""),
        "period": [d.get("startDate", ""), d.get("endDate", "")],
        "publications": len(d.get("publications") or []),
        "doi": d.get("doi") or None,
        "sources": [{"documentId": f"{acc}/metadata", "title": f"{name}: NASA PSI record", "url": f"https://psi.nasa.gov/physci/repo/data/investigations/{acc}"}],
        "generator": EXTRACTIVE,
    }


async def store(conn, kind: str, subject: str, generator: str, content: dict, data_generation: str) -> None:
    await conn.execute(
        """INSERT INTO summaries (kind, subject, generator, content, data_generation) VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (kind, subject, generator) DO UPDATE SET content = EXCLUDED.content, data_generation = EXCLUDED.data_generation, created_at = now()""",
        (kind, subject, generator, Jsonb(content), data_generation))


async def get(pool, kind: str, subject: str) -> list[dict]:
    """All stored versions for a subject; LLM versions first, then extractive."""
    async with pool.connection() as c:
        rows = await (await c.execute(
            """SELECT generator, content, data_generation AS "dataGeneration", created_at AS "createdAt" FROM summaries
               WHERE kind = %s AND subject = %s ORDER BY (generator = %s), created_at DESC""", (kind, subject, EXTRACTIVE))).fetchall()
    return rows
