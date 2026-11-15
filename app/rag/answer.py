"""
Cited answers for POST /ask.

Two generators, both grounded only in retrieved NASA PSI passages:
  * "extractive" (always available, offline): picks the sentences that best match the question and
    cites each one [n] -> document + page. Nothing is paraphrased, so nothing can be invented.
  * "claude" (when ANTHROPIC_API_KEY is set): Claude answers from the passages, sent as search_result
    blocks with citations enabled, so every claim carries a document/page citation from the API itself.

Every answer goes through a number guard: each number in the answer must appear in a cited passage
(or in the question). Numbers that do not are listed in `unverifiedNumbers`, and the answer is marked.
"""
from __future__ import annotations

import logging
import math
import re

from ..text import is_boilerplate, is_reference, numbers, sentences, tokenize
from .retriever import Passage

log = logging.getLogger("fif.answer")

SYSTEM = """You answer questions about spacecraft and habitat fire safety for NASA mission designers, using only the numbered NASA Physical Sciences Informatics (PSI) passages provided as search results.

Rules:
- Use only facts stated in the passages. Cite every factual sentence.
- Never invent or compute new numbers, dates or results; quote numbers exactly as the passages give them, with their units.
- If the passages do not answer the question, say so plainly and state what they do cover.
- Say which investigation each finding comes from (for example FLEX, BASS-II, Saffire, ACME CFI-G).
- Be concise: at most about 180 words, in plain prose, with no headings."""


def number_guard(answer: str, question: str, cited: list[Passage]) -> list[str]:
    allowed = numbers(question)
    for p in cited:
        allowed |= numbers(p.text) | numbers(p.title) | numbers(p.section)
    allowed |= {str(i) for i in range(1, len(cited) + 1)}  # citation markers [n]
    return sorted(n for n in numbers(answer) if n not in allowed)


def extractive(question: str, passages: list[Passage], max_sentences: int = 4) -> dict:
    q = set(tokenize(question))
    df = {}
    for p in passages:
        for t in set(tokenize(p.text)):
            df[t] = df.get(t, 0) + 1
    cands = []
    wants_pubs = bool(set(tokenize("publication paper article reference")) & q)
    for i, p in enumerate(passages):
        if p.section == "Publications" and not wants_pubs:
            continue
        for s in sentences(p.text):
            if is_reference(s) or is_boilerplate(s):
                continue
            s = re.sub(r"^\[\d+\]\s*", "", s)
            toks = set(tokenize(s))
            hit = toks & q
            if len(hit) < min(2, len(q)):  # a sentence must share at least two content terms with the question
                continue
            w = sum(math.log(1 + len(passages) / df.get(t, 1)) for t in hit)
            cands.append((w * (1 + 0.15 * (len(passages) - i) / len(passages)) / math.sqrt(1 + len(toks) / 25), i, s))
    cands.sort(key=lambda x: -x[0])
    chosen, used_text = [], set()
    for score, i, s in cands:
        key = s[:80]
        if key in used_text:
            continue
        used_text.add(key)
        chosen.append((i, s))
        if len(chosen) >= max_sentences:
            break
    if not chosen:
        return {"answer": "", "cited": []}
    order = []
    for i, _ in chosen:
        if i not in order:
            order.append(i)
    num = {i: n + 1 for n, i in enumerate(order)}
    text = " ".join(f"{s.rstrip()} [{num[i]}]" for i, s in chosen)
    return {"answer": text, "cited": [passages[i] for i in order]}


async def with_claude(client, model: str, question: str, passages: list[Passage]) -> dict:
    """Grounded answer with API-native citations. Returns {"answer", "cited", "model"}; raises on API errors."""
    content = [{
        "type": "search_result",
        "source": p.citation()["url"] + (f"#page={p.page}" if p.kind == "pdf" else ""),
        "title": f"{p.title} ({p.accession}" + (f", page {p.page})" if p.kind == "pdf" else f", {p.section or 'PSI record'})"),
        "content": [{"type": "text", "text": p.text}],
        "citations": {"enabled": True},
    } for p in passages]
    content.append({"type": "text", "text": f"Question: {question}"})
    resp = await client.beta.messages.create(
        model=model, max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        thinking={"type": "adaptive"}, output_config={"effort": "medium"},
        system=SYSTEM, messages=[{"role": "user", "content": content}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("the model declined this request")
    order: list[int] = []
    parts: list[str] = []
    for block in resp.content:
        if block.type != "text":
            continue
        marks = []
        for c in getattr(block, "citations", None) or []:
            idx = getattr(c, "search_result_index", None)
            if idx is None or not 0 <= idx < len(passages):
                continue
            if idx not in order:
                order.append(idx)
            m = f"[{order.index(idx) + 1}]"
            if m not in marks:
                marks.append(m)
        parts.append(block.text + ("".join(" " + m for m in marks) if marks else ""))
    return {"answer": "".join(parts).strip(), "cited": [passages[i] for i in order], "model": resp.model}
