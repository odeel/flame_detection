"""
Rubric ranking of PSI investigations for a crew habitat (POST /rank, /habitats/{id}).

Every component is computed from NASA data and is reported with its reason, so a score can be audited:

  atmosphere   Measured test rows at the habitat's O2 (+-3 points) and pressure (+-20 kPa) -> 1.0;
               tested at or above its O2 -> 0.65 (conservative evidence); within 6 points or 80% of it -> 0.35; else 0.
  gravity      Microgravity data for 0-g habitats -> 1.0. For the Moon and Mars, microgravity and 1-g results
               only bound partial gravity -> 0.7, except an electric-field buoyancy proxy (E-FIELD Flames) -> 1.0.
  ventilation  Tested flow range spans the habitat's ventilation (or includes quiescent tests for 0 cm/s) -> 1.0,
               no flow recorded -> 0.5, outside the range -> 0.3.
  scale        Spacecraft-scale fires (Saffire) -> 1.0; sealed-volume effects for small cabins -> 1.0; else 0.5.
  topic        BM25 relevance of the investigation's PSI text to a fire-safety query for the habitat (0..1).
  data         Richness of evidence: log-scaled test rows (70%) and parsed documents (30%).

Default weights: atmosphere 0.35, gravity 0.15, ventilation 0.10, scale 0.10, topic 0.20, data 0.10.
In oxygen-enriched habitats (O2 >= 30%) the atmosphere is the defining hazard: atmosphere 0.40, topic 0.15.
"""
from __future__ import annotations

import math
from collections import Counter

from .habitats import LARGE_SCALE, PARTIAL_GRAVITY_PROXY, PILLAR_OF
from .text import SYN_INDEX, tokenize

COMPONENTS = ["atmosphere", "gravity", "ventilation", "scale", "topic", "data"]
DEFAULT_WEIGHTS = {"atmosphere": 0.35, "gravity": 0.15, "ventilation": 0.10, "scale": 0.10, "topic": 0.20, "data": 0.10}
ENRICHED_WEIGHTS = {"atmosphere": 0.40, "gravity": 0.15, "ventilation": 0.10, "scale": 0.10, "topic": 0.15, "data": 0.10}
SEALED = ("pressure rise", "o2 depletion", "oxygen depletion", "sealed", "cabin atmosphere", "closed volume", "chamber pressure")


def default_weights(habitat: dict | None) -> dict:
    return dict(ENRICHED_WEIGHTS if habitat and habitat["o2"] >= 30 else DEFAULT_WEIGHTS)


def habitat_query(h: dict | None) -> str:
    if not h:
        return "spacecraft fire safety flammability ignition flame spread extinction suppression detection smoke"
    q = f"fire safety {h['label']} {h['examples']} flammability ignition flame spread extinction"
    if h["o2"] > 23:
        q += " oxygen enriched elevated oxygen concentration reduced pressure"
    if 0 < h["gravity"] < 1:
        q += " partial gravity lunar martian buoyancy"
    if h["volume"] == "small":
        q += " sealed cabin pressure rise oxygen depletion"
    return q


def doc_text(doc: dict) -> str:
    return " ".join(str(doc.get(k) or "") for k in ("title", "acronym", "objectives", "hypothesis", "approach", "earthBenefits", "hardware")) + \
        " " + " ".join(doc.get("keywords") or [])


def topic_scores(invs: list[dict], query: str) -> dict[str, float]:
    """BM25 of each investigation's PSI text against the query, normalized to 0..1."""
    toks = {i["accession"]: tokenize(doc_text({**i["doc"], "title": i["title"], "acronym": i["acronym"]})) for i in invs}
    n = len(toks) or 1
    df = Counter(t for ts in toks.values() for t in set(ts))
    avg = sum(len(t) for t in toks.values()) / n
    q = {t: 1.0 for t in tokenize(query)}
    for t in list(q):
        for s in SYN_INDEX.get(t, []):
            q.setdefault(s, 0.4)
    raw = {}
    for acc, ts in toks.items():
        tf, dl, s = Counter(ts), len(ts) or 1, 0.0
        for t, w in q.items():
            f = tf.get(t)
            if f:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += w * idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * dl / avg))
        raw[acc] = s
    top = max(raw.values() or [1]) or 1
    return {a: round(v / top, 4) for a, v in raw.items()}


def near_atmosphere(rows: list[dict], h: dict) -> int:
    return sum(1 for r in rows if r["o2_pct"] is not None and abs(r["o2_pct"] - h["o2"]) <= 3
               and (r["pressure_kpa"] is None or abs(r["pressure_kpa"] - h["pressure"]) <= 20))


def score_investigation(inv: dict, h: dict | None, stats: dict | None, rows: list[dict], topic: float, docs: int, max_rows: int, weights: dict) -> dict:
    acc, name = inv["accession"], inv["acronym"] or inv["accession"]
    text = doc_text(inv["doc"]).lower()
    reasons, comp = [], {}
    # atmosphere
    if h is None:
        comp["atmosphere"] = 0.5
    elif not stats or stats["n_o2"] == 0:
        comp["atmosphere"] = 0.0
        reasons.append("no oxygen level recorded in its PSI test matrix")
    else:
        near = near_atmosphere(rows, h)
        if near:
            comp["atmosphere"] = 1.0
            reasons.append(f"{near} test points at {h['o2']:g}% O2 / {h['pressure']:g} kPa (within 3 points and 20 kPa)")
        elif stats["o2_max"] >= h["o2"]:
            comp["atmosphere"] = 0.65
            reasons.append(f"tested up to {stats['o2_max']:g}% O2 (habitat {h['o2']:g}%): conservative evidence")
        elif stats["o2_max"] >= h["o2"] - 6 or stats["o2_max"] >= 0.8 * h["o2"]:
            comp["atmosphere"] = 0.35
            reasons.append(f"closest O2 tested {stats['o2_max']:g}% (habitat {h['o2']:g}%)")
        else:
            comp["atmosphere"] = 0.0
            reasons.append(f"O2 tested only up to {stats['o2_max']:g}%")
    # gravity
    if h is None or h["gravity"] == 0:
        comp["gravity"] = 1.0
        if h is not None:
            reasons.append("microgravity data")
    elif acc in PARTIAL_GRAVITY_PROXY:
        comp["gravity"] = 1.0
        reasons.append("mimics partial gravity with electric-field body forces")
    else:
        comp["gravity"] = 0.7
        reasons.append(f"microgravity result bounds {h['gravity']:g} g (no partial-gravity data in PSI)")
    # ventilation
    if not stats or stats["flow_min"] is None:
        comp["ventilation"] = 0.5
    elif h is not None and h["flow"] == 0 and stats["flow_min"] == 0:
        comp["ventilation"] = 1.0
        reasons.append("includes quiescent tests")
    elif h is not None and stats["flow_min"] <= h["flow"] <= stats["flow_max"]:
        comp["ventilation"] = 1.0
        reasons.append(f"flow {stats['flow_min']:g}-{stats['flow_max']:g} cm/s spans {h['flow']:g} cm/s ventilation")
    else:
        comp["ventilation"] = 0.3
    # scale
    comp["scale"] = 0.5
    if acc in LARGE_SCALE:
        comp["scale"] = 1.0
        reasons.append("spacecraft-scale fire (Saffire, aboard Cygnus)")
    elif h is not None and h["volume"] == "small" and any(k in text for k in SEALED):
        comp["scale"] = 1.0
        reasons.append("reports sealed-volume effects (pressure, oxygen)")
    comp["topic"] = topic
    n_rows = stats["n"] if stats else 0
    comp["data"] = round(0.7 * (math.log1p(n_rows) / math.log1p(max_rows) if max_rows else 0) + 0.3 * min(1.0, docs / 5), 4)
    if n_rows:
        reasons.append(f"{n_rows} normalized test points" + (f", {docs} parsed document(s)" if docs else ""))
    total = sum(weights.values()) or 1
    score = 100 * sum(weights[k] * comp[k] for k in COMPONENTS) / total
    return {"accession": acc, "acronym": name, "title": inv["title"], "score": round(score, 1),
            "components": {k: round(v, 3) for k, v in comp.items()}, "reasons": reasons, "pillars": PILLAR_OF.get(acc, []),
            "envelope": {k: stats[k] for k in ("o2_min", "o2_max", "p_min", "p_max", "flow_min", "flow_max")} if stats else None,
            "doi": inv["doc"].get("doi") or None, "url": f"https://psi.nasa.gov/physci/repo/data/investigations/{acc}"}


def rank(invs: list[dict], h: dict | None, stats: dict, rows_by_acc: dict, docs_by_acc: dict, weights: dict | None = None,
         query: str | None = None, pillar: str | None = None, min_tests: int = 0) -> dict:
    w = default_weights(h)
    if weights:
        for k, v in weights.items():
            if k in w:
                w[k] = max(0.0, float(v))
    topics = topic_scores(invs, query or habitat_query(h))
    max_rows = max((s["n"] for s in stats.values()), default=0)
    items = []
    for inv in invs:
        acc = inv["accession"]
        if pillar and pillar not in PILLAR_OF.get(acc, []):
            continue
        if min_tests and (stats.get(acc, {}) or {}).get("n", 0) < min_tests:
            continue
        items.append(score_investigation(inv, h, stats.get(acc), rows_by_acc.get(acc, []), topics.get(acc, 0.0), docs_by_acc.get(acc, 0), max_rows, w))
    items.sort(key=lambda x: (-x["score"], x["accession"]))
    for i, it in enumerate(items, 1):
        it["rank"] = i
    return {"weights": {k: round(v, 3) for k, v in w.items()}, "items": items}
