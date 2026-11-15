"""Tokenizer, light stemmer, stop words and fire-safety synonyms (same rules as assets/js/engine.js)."""
from __future__ import annotations

import re

STOP = set(("a about above after again against all also am an and any are as at be because been before being below between both but by can could did do "
            "does doing down during each few for from further had has have having he her here hers him his how i if in into is it its itself just more most "
            "much my no nor not now of off on once only or other our out over own same she should so some such than that the their them then there these they "
            "this those through to too under until up very was we were what when where which while who whom why will with would you your may might within "
            "without across along among per via upon whose thereby rather even well using used use study studied investigation experiment experiments tested "
            "test tests measured results result showed show shows based new first one two three provides provide data also including include includes "
            "conditions condition").split())

_RULES = [(re.compile(p), r) for p, r in [(r"ies$", "y"), (r"sses$", "ss"), (r"ness$", ""), (r"ments?$", ""), (r"ations?$", "ate"), (r"ings?$", ""),
                                          (r"edly$", ""), (r"ed$", ""), (r"ers?$", ""), (r"ly$", ""), (r"es$", "e"), (r"s$", "")]]


def stem(w: str) -> str:
    if len(w) <= 4:
        return w
    for rx, rep in _RULES:
        if rx.search(w):
            out = rx.sub(rep, w)
            if len(out) >= 3:
                return out
    return w


def tokenize(text: str) -> list[str]:
    toks = re.split(r"[\s\-]+", re.sub(r"[^a-z0-9\s\-]", " ", str(text or "").lower()))
    return [stem(t) for t in toks if t and len(t) > 1 and t not in STOP and not t.isdigit()]


SYNONYMS = [
    ["extinguisher", "suppression", "suppress", "extinguish", "extinguishment", "agent"],
    ["detector", "detection", "sensor", "alarm", "monitor"],
    ["smoke", "soot", "aerosol", "particulate", "particle"],
    ["cabin", "habitat", "module", "spacecraft", "crew", "vehicle"],
    ["flammability", "flammable", "ignition", "burn", "combustion"],
    ["oxygen", "o2", "enriched"],
    ["ventilation", "flow", "airflow", "coflow"],
    ["model", "predictive", "prediction", "simulation", "validation"],
    ["cleanup", "filter", "sorbent", "scrubber"],
    ["wire", "electrical", "insulation", "overheating", "cable"],
    ["wildfire", "wildland", "vegetation", "forest", "bushfire", "grass", "grasses", "litter", "peat"],
    ["hospital", "medical", "hyperbaric", "patient"],
    ["building", "home", "house", "residential", "furniture"],
    ["upholstery", "upholstered", "furniture", "furnishings", "cushion", "sofa", "mattress"],
    ["earth", "terrestrial", "ground"],
]
SYN_INDEX: dict[str, list[str]] = {}
for _g in SYNONYMS:
    _stems = [stem(w) for w in _g]
    for _s in _stems:
        SYN_INDEX[_s] = _stems

NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)*(?:\.\d+)?")


def numbers(text: str) -> set[str]:
    """Normalized numbers in a text ("1,000" -> "1000", "21.50" -> "21.5"), used by the citation number guard."""
    out = set()
    for m in NUMBER.findall(text or ""):
        s = m.replace(",", "")
        try:
            v = float(s)
        except ValueError:
            continue
        out.add(f"{v:g}")
    return out


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")


LIST_ITEM = re.compile(r"\n+|\s(?=\(?\d{1,2}[.)]\s+[A-Z])")


def sentences(text: str, max_chars: int = 360) -> list[str]:
    """Sentences, also split at line breaks and numbered list items; overly long ones are cut at '; '."""
    out = []
    for block in LIST_ITEM.split(text or ""):
        for s in SENTENCE.split(block):
            s = re.sub(r"^\(?\d{1,2}[.)]\s+", "", s.strip())
            while len(s) > max_chars and "; " in s[:max_chars]:
                cut = s.rfind("; ", 0, max_chars)
                out.append(s[:cut + 1])
                s = s[cut + 2:]
            if 25 < len(s) <= max_chars * 1.5:
                out.append(s)
    return out


# Bibliography entries, figure/video captions and similar text that should never be quoted as an answer.
REFERENCE = re.compile(r"\bet al\b|\(\s*(19|20)\d{2}\s*\)\s*\d+\s*[-–]\s*\d+|\b(19|20)\d{2}\b[^.]{0,40}\b\d+\s*[-–]\s*\d+\b|\bdoi\b|"
                       r"\bProc(eedings)?\.|\bJ\. ?[A-Z]|\bVol\.|\bAIAA[- ]\d|\bCombustion and Flame\b|\bCombust\. Sci|\bpp\. ?\d", re.I)
CAPTION = re.compile(r"^(figure|fig\.|table|caption|video|photo|image)\b|CAPTION|NOT INCLUDED", re.I)


def is_reference(s: str) -> bool:
    return bool(REFERENCE.search(s))


def is_boilerplate(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    upper = sum(c.isupper() for c in letters) / max(1, len(letters))
    return bool(CAPTION.search(s)) or upper > 0.5 or s.count("  ") > 4


def bibliography_score(text: str) -> float:
    """Share of the passage's lines/sentences that look like reference-list entries (0..1)."""
    parts = [x for x in re.split(r"\n|(?<=\.)\s+(?=\[?\d|[A-Z]\.)", text) if len(x.strip()) > 20]
    return sum(1 for x in parts if is_reference(x)) / max(1, len(parts))
