"""
Printable fire-safety brief for one habitat (GET /brief/{habitat}): JSON, Markdown (copyable) or HTML (printable).

Contents, all derived from NASA PSI data:
  bottom line · design atmosphere · evidence counts · top-ranked investigations with reasons ·
  measured test evidence near the habitat atmosphere · priorities per pillar (prevention, detection,
  suppression) · evidence gaps · cited passages from PSI documents · sources with DOIs.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from .habitats import PILLARS


def gaps(h: dict, ranked: list[dict], near_rows: int, enriched_rows: int) -> list[str]:
    out = []
    if near_rows == 0:
        out.append(f"No PSI test point matches the {h['o2']:g}% O2 / {h['pressure']:g} kPa design atmosphere: new tests at this atmosphere are needed.")
    elif near_rows < 30:
        out.append(f"Only {near_rows} PSI test points match the design atmosphere: too few to validate models across materials.")
    if h["o2"] >= 30 and enriched_rows == 0:
        out.append("No material burned at or above the habitat's oxygen level in PSI data.")
    if 0 < h["gravity"] < 1:
        out.append(f"No partial-gravity ({h['gravity']:g} g) combustion data in PSI: microgravity and 1-g results only bound the behaviour.")
    if not any(r["components"]["scale"] == 1.0 and "spacecraft-scale" in " ".join(r["reasons"]) for r in ranked[:10]):
        out.append("Spacecraft-scale fire evidence (Saffire) does not cover this atmosphere.")
    if h["o2"] >= 90:
        out.append("Pure-oxygen environments are the most severe case; the closest PSI evidence is ACME CFI-G at up to about 85% O2 (inverse flames).")
    return out


def build(h: dict, ranked: list[dict], test_evidence: list[dict], near_rows: int, enriched_rows: int, passages: list[dict], top: int = 8) -> dict:
    head = ranked[:top]
    by_pillar = {}
    for p, desc in PILLARS.items():
        items = [r for r in ranked if p in r["pillars"]][:3]
        by_pillar[p] = {"description": desc, "investigations": [{"accession": r["accession"], "acronym": r["acronym"], "score": r["score"]} for r in items]}
    atm_full = sum(1 for r in ranked if r["components"]["atmosphere"] == 1.0)
    bottom = (f"{atm_full} of {len(ranked)} PSI combustion investigations have test points at the {h['label'].lower()} design atmosphere "
              f"({h['o2']:g}% O2, {h['pressure']:g} kPa); {near_rows} measured test points match it and {enriched_rows} were run at or above its oxygen level. "
              f"Most relevant: " + ", ".join(r["acronym"] for r in head[:3]) + ".")
    return {
        "habitat": h, "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bottomLine": bottom,
        "evidence": {"investigationsAtAtmosphere": atm_full, "testPointsAtAtmosphere": near_rows, "testPointsAtOrAboveO2": enriched_rows},
        "investigations": [{k: r[k] for k in ("rank", "accession", "acronym", "title", "score", "reasons", "pillars", "doi", "url")} for r in head],
        "testEvidence": test_evidence,
        "priorities": by_pillar,
        "gaps": gaps(h, ranked, near_rows, enriched_rows),
        "passages": passages,
        "sources": [{"accession": r["accession"], "acronym": r["acronym"], "doi": r["doi"], "url": r["url"]} for r in head],
        "method": "Rubric ranking over NASA PSI records and normalized test matrices; passages retrieved from PSI documents. See /docs.",
    }


def _rng(a, b, unit):
    if a is None:
        return "n/a"
    return f"{a:g}{unit}" if a == b else f"{a:g}–{b:g}{unit}"


def to_markdown(b: dict) -> str:
    h = b["habitat"]
    out = [f"# Fire-safety brief: {h['label']}", "",
           f"*{h['examples']}. Design atmosphere {h['o2']:g}% O2 at {h['pressure']:g} kPa, {h['gravity']:g} g, ventilation {h['flow']:g} cm/s.*", "",
           f"> {h['note']}", "", "## Bottom line", "", b["bottomLine"], "", "## Most relevant investigations", "",
           "| # | Investigation | Score | Why |", "|---|---|---|---|"]
    for r in b["investigations"]:
        out.append(f"| {r['rank']} | {r['acronym']} ({r['accession']}) | {r['score']:g} | {'; '.join(r['reasons'][:3])} |")
    out += ["", "## Measured test evidence near this atmosphere", ""]
    if b["testEvidence"]:
        out += ["| Investigation | Test points | Fuels | O2 | Pressure | Outcomes |", "|---|---|---|---|---|---|"]
        for t in b["testEvidence"]:
            out.append(f"| {t['acronym']} | {t['n']} | {', '.join(t['fuels'][:4])} | {_rng(t['o2_min'], t['o2_max'], '%')} | {_rng(t['p_min'], t['p_max'], ' kPa')} | {'; '.join(t['outcomes'][:3]) or '—'} |")
    else:
        out.append("No PSI test points match this atmosphere.")
    out += ["", "## Priorities by fire-safety pillar", ""]
    for p, v in b["priorities"].items():
        out.append(f"- **{p.capitalize()}** ({v['description']}): " + (", ".join(f"{i['acronym']}" for i in v["investigations"]) or "no PSI evidence"))
    out += ["", "## Evidence gaps", ""] + [f"- {g}" for g in b["gaps"]]
    if b["passages"]:
        out += ["", "## From NASA PSI documents", ""]
        for i, p in enumerate(b["passages"], 1):
            loc = f", page {p['page']}" if p.get("page") else ""
            out.append(f"{i}. “{p['text']}” — {p['title']} ({p['accession']}{loc})")
    out += ["", "## Sources", ""] + [f"- {s['acronym']} ({s['accession']}): " + (f"https://doi.org/{s['doi']}" if s["doi"] else s["url"]) for s in b["sources"]]
    out += ["", f"*Generated {b['generatedAt']} by Flame in Freefall from NASA Physical Sciences Informatics data (CC0).*"]
    return "\n".join(out) + "\n"


CSS = """
:root{--ink:#1a1d24;--muted:#5b6170;--line:#d9dce3;--accent:#c2410c;--bg:#ffffff}
@media (prefers-color-scheme: dark){:root{--ink:#e8eaf0;--muted:#a3a9b6;--line:#343a46;--accent:#fb923c;--bg:#14161b}}
body{font:15px/1.55 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;color:var(--ink);background:var(--bg);max-width:900px;margin:32px auto;padding:0 16px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.sub{color:var(--muted);margin:0 0 16px}.note{border-left:3px solid var(--accent);padding:6px 12px;color:var(--muted)}
.kpis{display:flex;gap:12px;flex-wrap:wrap}.kpi{border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:150px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.kpi span{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}
blockquote{margin:8px 0;padding:0 12px;border-left:3px solid var(--line);color:var(--muted)}
.foot{color:var(--muted);font-size:12px;margin-top:32px}
@media print{body{margin:0;max-width:none}a{color:inherit;text-decoration:none}h2{break-after:avoid}tr{break-inside:avoid}}
"""


def to_html(b: dict) -> str:
    e = html.escape
    h = b["habitat"]
    rows = "".join(f"<tr><td class=num>{r['rank']}</td><td><a href='{e(r['url'])}'>{e(r['acronym'])}</a><br><small>{e(r['accession'])}</small></td>"
                   f"<td class=num>{r['score']:g}</td><td>{e('; '.join(r['reasons'][:3]))}</td></tr>" for r in b["investigations"])
    ev = "".join(f"<tr><td>{e(t['acronym'])}</td><td class=num>{t['n']}</td><td>{e(', '.join(t['fuels'][:4]))}</td><td>{e(_rng(t['o2_min'], t['o2_max'], '%'))}</td>"
                 f"<td>{e(_rng(t['p_min'], t['p_max'], ' kPa'))}</td><td>{e('; '.join(t['outcomes'][:3]) or '—')}</td></tr>" for t in b["testEvidence"]) \
        or "<tr><td colspan=6>No PSI test points match this atmosphere.</td></tr>"
    pr = "".join(f"<li><b>{e(p.capitalize())}</b>: {e(v['description'])} — {e(', '.join(i['acronym'] for i in v['investigations']) or 'no PSI evidence')}</li>"
                 for p, v in b["priorities"].items())
    gp = "".join(f"<li>{e(g)}</li>" for g in b["gaps"])
    ps = "".join(f"<blockquote>“{e(p['text'])}”<br><small>{e(p['title'])} ({e(p['accession'])}{', page ' + str(p['page']) if p.get('page') else ''})</small></blockquote>"
                 for p in b["passages"])
    src = "".join(f"<li>{e(s['acronym'])} ({e(s['accession'])}): <a href='{e('https://doi.org/' + s['doi'] if s['doi'] else s['url'])}'>"
                  f"{e('doi:' + s['doi'] if s['doi'] else s['url'])}</a></li>" for s in b["sources"])
    k = b["evidence"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fire-safety brief: {e(h['label'])}</title><style>{CSS}</style></head><body>
<h1>Fire-safety brief: {e(h['label'])}</h1>
<p class="sub">{e(h['examples'])} · {h['o2']:g}% O<sub>2</sub> at {h['pressure']:g} kPa · {h['gravity']:g} g · ventilation {h['flow']:g} cm/s</p>
<p class="note">{e(h['note'])}</p>
<h2>Bottom line</h2><p>{e(b['bottomLine'])}</p>
<div class="kpis"><div class="kpi"><b>{k['investigationsAtAtmosphere']}</b><span>investigations at this atmosphere</span></div>
<div class="kpi"><b>{k['testPointsAtAtmosphere']}</b><span>test points at this atmosphere</span></div>
<div class="kpi"><b>{k['testPointsAtOrAboveO2']}</b><span>test points at or above its O<sub>2</sub></span></div></div>
<h2>Most relevant investigations</h2><table><tr><th>#</th><th>Investigation</th><th>Score</th><th>Why</th></tr>{rows}</table>
<h2>Measured test evidence near this atmosphere</h2><table><tr><th>Investigation</th><th>Tests</th><th>Fuels</th><th>O<sub>2</sub></th><th>Pressure</th><th>Outcomes</th></tr>{ev}</table>
<h2>Priorities by fire-safety pillar</h2><ul>{pr}</ul>
<h2>Evidence gaps</h2><ul>{gp}</ul>
{'<h2>From NASA PSI documents</h2>' + ps if ps else ''}
<h2>Sources</h2><ul>{src}</ul>
<p class="foot">Generated {e(b['generatedAt'])} by Flame in Freefall from NASA Physical Sciences Informatics data (CC0). {e(b['method'])}</p>
</body></html>"""
