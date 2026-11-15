"""
Test-row extraction: every PSI experimental table becomes normalized rows
    fuel · O2 (vol %) · pressure (kPa) · flow (cm/s) · diluents · text conditions · outcome · measured results

Column roles are detected from header names and values are normalized per cell, because PSI tables
mix mole fractions and percentages, atm / bar / mmHg / kPa, and text such as "~ 21.5" or "20 cm/s".
Each row keeps its source (accession, table id, row index), so every value can be traced back to NASA's table.
"""
from __future__ import annotations

import math
import re

NUM = re.compile(r"(?<![A-Za-z\d.])\d*\.?\d+(?:e[-+]?\d+)?(?![A-Za-z]*\d)", re.I)

FUEL_COL = re.compile(r"^(fuel|fuel type|fuel sample material|sample material|material|sample \(fuel type\)|sample type|fuel bottle)$", re.I)
O2_COL = re.compile(r"\bx ?o2\b|o2 ?%|percent o2|oxygen|o2 mole|calibrated initial o2|^o initial|^xo2", re.I)
O2_EXCLUDE = re.compile(r"final|after|mg/s|sccm|\brate\b|mass|mfc|co2|\bco\b", re.I)
P_COL = re.compile(r"pressure|^p ?\(|^p(init|mean)|approx p", re.I)
FLOW_COL = re.compile(r"air flow|air rate|flow velocity|inlet velocity", re.I)
OUTCOME_COL = re.compile(r"hot ignition|flames ignited|test end|self.?ext|cool flame\?|^result|^outcome|extinction mode", re.I)
CONDITION_COL = re.compile(r"^(direction|flow direction|atmosphere\*?|ambient gas mixture|flame type|mesh polarity|fiber)$", re.I)
MEASURE_COL = re.compile(r"burning rate|burn rate|extinction diameter|spread rate|spread length|burn length|weight loss|rt/r0|burn time|tad \(k\)|"
                         r"droplet initial diameter|initial droplet diameter|nozzle|burner size|sample thickness|samle thickness", re.I)
DILUENT_COL = re.compile(r"^(co|co2|he|n)\s+initial ambient|^(helium|nitrogen)$", re.I)
FUEL_IN_HEADER = re.compile(r"\bX ?(C2H4|CH4|C2H6|C3H8|H2)\b")


def numbers_in(cell) -> list[float]:
    """All numbers in a messy cell: "21.5 - 21.7", "~ 21.5", "0.17; 0.21;0.25", "1.25 atm", "3400%"."""
    txt = str(cell or "")
    vals = [float(x) for x in NUM.findall(re.sub(r",(?=\d{3}\b)", "", txt))]
    pct = "%" in txt
    return [x / 100 if pct and x > 100 else x for x in vals if math.isfinite(x)]


def first_number(cell):
    v = numbers_in(cell)
    return v[0] if v else None


def pressure_factor(name: str, cell: str, sample: float) -> float:
    s = f"{name} {cell}".lower()
    if re.search(r"mm ?hg", s):
        return 0.133322
    if re.search(r"\bbar\b", s):
        return 100.0
    if "atm" in s:
        return 101.325
    if "psi" in s:
        return 6.89476
    if "kpa" in s:
        return 1.0
    return 101.325 if sample <= 5 else 1.0  # unlabelled small values are atmospheres


def _pick(cols, rx, exclude, prefer=None) -> int:
    idx = [(c, j) for j, c in enumerate(cols) if rx.search(c) and not exclude.search(c)]
    if not idx:
        return -1
    if prefer:
        for c, j in idx:
            if prefer.search(c):
                return j
    return idx[0][1]


def table_roles(columns: list[str]) -> dict:
    cols = [str(c).strip() for c in columns]
    fuel_hdr = FUEL_IN_HEADER.search(" ".join(cols))
    return {
        "fuel": next((j for j, c in enumerate(cols) if FUEL_COL.match(c)), -1),
        "o2": _pick(cols, O2_COL, O2_EXCLUDE, re.compile(r"init|before", re.I)),
        "pressure": _pick(cols, P_COL, re.compile(r"final", re.I), re.compile(r"pmean|approx p|ambient", re.I)),
        "flow": _pick(cols, FLOW_COL, re.compile(r"mg/s|sccm", re.I)),
        "diluents": [(c, j) for j, c in enumerate(cols) if DILUENT_COL.search(c)],
        "outcome": [(c, j) for j, c in enumerate(cols) if OUTCOME_COL.search(c)],
        "conditions": [(c, j) for j, c in enumerate(cols) if CONDITION_COL.match(c)],
        "measures": [(c, j) for j, c in enumerate(cols) if MEASURE_COL.search(c)],
        "fuel_from_header": fuel_hdr.group(1) if fuel_hdr else "",
    }


def _diluent_name(col: str) -> str:
    c = col.lower()
    if c.startswith(("co2", "co initial")):  # FLEX labels its CO2 column "CO initial ambient composition"
        return "CO2"
    if c.startswith(("he", "helium")):
        return "He"
    if c.startswith(("n ", "n initial", "nitrogen", "n2")):
        return "N2"
    return col


def _r(x, d=3):
    return None if x is None or not math.isfinite(x) else round(x, d)


def extract_rows(columns: list[str], rows: list[list[str]]) -> list[dict]:
    r = table_roles(columns)
    out = []
    for i, row in enumerate(rows):
        def cell(j):
            return str(row[j]).strip() if 0 <= j < len(row) and row[j] is not None else ""

        o2 = first_number(cell(r["o2"]))
        if o2 is not None:
            o2 = o2 * 100 if o2 <= 1 else o2
            if not 0 < o2 <= 100:
                o2 = None
        p_raw = first_number(cell(r["pressure"]))
        pressure = p_raw * pressure_factor(columns[r["pressure"]], cell(r["pressure"]), p_raw) if p_raw and p_raw > 0 else None
        flow = first_number(cell(r["flow"]))
        if flow is not None and not 0 <= flow < 1000:
            flow = None
        diluents = {}
        for c, j in r["diluents"]:
            v = first_number(cell(j))
            if v is not None and v > 0:
                diluents[_diluent_name(c)] = _r(v * 100 if v <= 1 else v, 2)
        conditions = {c.rstrip("*"): cell(j)[:120] for c, j in r["conditions"] if cell(j) and cell(j) != "-"}
        outcome = "; ".join(f"{c}: {cell(j)}" for c, j in r["outcome"] if cell(j) and cell(j) != "-")[:500]
        measures = {c: v for c, j in r["measures"] if (v := first_number(cell(j))) is not None}
        fuel = (cell(r["fuel"]) or r["fuel_from_header"])[:200]
        if not fuel and o2 is None and pressure is None and flow is None and not outcome and not measures:
            continue
        out.append({"row_index": i, "fuel": fuel, "o2_pct": _r(o2, 2), "pressure_kpa": _r(pressure, 2), "flow_cm_s": _r(flow, 2),
                    "diluents": diluents, "conditions": conditions, "outcome": outcome, "measures": measures})
    return out
