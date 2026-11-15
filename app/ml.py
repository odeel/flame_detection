"""
Trained PSI models: storage in PostgreSQL and prediction.

Models are trained by the shared JavaScript code (assets/js/training.js, run with `npm run train` or
POST /api/v1/admin/train) and stored as JSON artifacts in the `models` table. Prediction here mirrors
assets/js/ml.js + training.js exactly, so the API and the in-browser dashboard return the same numbers.
"""
from __future__ import annotations

import json
import math
import re

from .config import REPO_ROOT
from .db import bump

MODELS_JS = REPO_ROOT / "assets" / "data" / "models.js"


# ------------------------------------------------------------------ prediction (port of ml.js)
def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def _linear_score(mdl: dict, x: list[float]) -> float:
    mu, sd, w = mdl["scaler"]["mu"], mdl["scaler"]["sd"], mdl["w"]
    s = w[0]
    for j, v in enumerate(x):
        s += w[j + 1] * (v - mu[j]) / sd[j]
    return s


def _tree_predict(node: dict, x: list[float]) -> float:
    while "f" in node:
        node = node["l"] if x[node["f"]] <= node["t"] else node["r"]
    return node["v"]


def predict_model(mdl: dict, x: list[float]) -> float:
    """Probability for classifiers, value for regressors."""
    if mdl["type"] == "logistic":
        return _sigmoid(_linear_score(mdl, x))
    if mdl["type"] == "ridge":
        return _linear_score(mdl, x)
    trees = mdl["trees"]
    return sum(_tree_predict(t, x) for t in trees) / len(trees)


def _number(v) -> float | None:
    if v is None or v == "" or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def predict_artifact(art: dict, inputs: dict) -> dict:
    """Predict from a {featureKey: value} mapping; missing or invalid keys use the training medians."""
    x = []
    for f in art["features"]:
        v = _number((inputs or {}).get(f["key"]))
        x.append(f["median"] if v is None else v)
    extrapolated = [f["key"] for f, v in zip(art["features"], x) if f.get("kind") == "numeric" and (v < f["min"] or v > f["max"])]
    return {"value": predict_model(art["model"], x), "input": x, "extrapolated": extrapolated}


def format_result(art: dict, r: dict) -> dict:
    v = round(r["value"], 4)
    if art["task"] == "classification":
        t = art["target"]
        return {"probability": v, "label": t["positive"] if r["value"] >= 0.5 else t["negative"], "extrapolated": r["extrapolated"]}
    return {"value": v, "unit": art["target"].get("unit"), "extrapolated": r["extrapolated"]}


def card(art: dict) -> dict:
    """Model card: the artifact without the serialized model and out-of-fold arrays."""
    return {k: v for k, v in art.items() if k not in ("model", "oof")}


# ------------------------------------------------------------------ storage
def bundled_models() -> list[dict]:
    """Model artifacts committed in assets/data/models.js (written by `npm run train`)."""
    if not MODELS_JS.exists():
        return []
    m = re.search(r"var MODELS = (\[.*\]);\s*\n", MODELS_JS.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1)) if m else []


async def seed_if_empty(conn) -> int:
    """Load the committed model artifacts into an empty `models` table (one active version each)."""
    if (await (await conn.execute("SELECT count(*) AS n FROM models")).fetchone())["n"]:
        return 0
    n = 0
    for art in bundled_models():
        best = next((c for c in art["cv"]["candidates"] if c["algorithm"] == art["algorithm"]), None)
        version = int(art.get("version") or 1)
        await conn.execute(
            """INSERT INTO models (id, version, title, task, algorithm, primary_metric, score, n, data_hash, trained_at, artifact, active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true) ON CONFLICT DO NOTHING""",
            (art["id"], version, art["title"], art["task"], art["algorithm"], art["cv"]["primaryMetric"],
             best["metrics"].get(art["cv"]["primaryMetric"]) if best else None, art["n"], art["dataHash"], art["trainedAt"],
             json.dumps({**art, "version": version})))
        n += 1
    if n:
        await bump(conn, "model_generation")
    return n
