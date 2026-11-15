"""Trained-model and Claude routes used by the dashboard (prefix /api/v1). Models live in PostgreSQL."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import interpret, ml

router = APIRouter()
ModelId = Annotated[str, Path(pattern=r"^[a-z0-9-]{1,64}$", examples=["flex-extinction"])]


class PredictRequest(BaseModel):
    inputs: dict[str, float] | Annotated[list[dict[str, float]], Field(max_length=500)] = Field(
        ..., description="Feature values by key (one object or a batch). Missing features use the training medians.",
        examples=[{"o2": 0.21, "pressure_atm": 1}])


class InterpretRequest(BaseModel):
    model_config = {"extra": "allow"}
    mode: Literal["investigation", "portfolio"] = "investigation"


def svc(req: Request):
    return req.app.state.services


@router.get("/models", tags=["models"], summary="Active models: model cards with metrics and explanations")
async def models(req: Request):
    return {"items": [ml.card(a) for a in await svc(req).active_models()]}


@router.get("/models/{model_id}", tags=["models"], summary="Model artifact (include=model adds the serialized model for client-side prediction)")
async def model(req: Request, model_id: ModelId, include: Literal["model", "none"] = "none", version: Annotated[int | None, Query(ge=1)] = None):
    s = svc(req)
    a = await s.model_version(model_id, version) if version else await s.active_model(model_id)
    if not a:
        raise HTTPException(404, "Model not found")
    return a if include == "model" else ml.card(a)


@router.get("/models/{model_id}/versions", tags=["models"], summary="Training history of a model")
async def model_versions(req: Request, model_id: ModelId):
    v = await svc(req).model_versions(model_id)
    if not v:
        raise HTTPException(404, "Model not found")
    return {"id": model_id, "versions": v}


@router.post("/models/{model_id}/predict", tags=["models"], summary="Predict with the active model version (predictions are logged)")
async def predict(req: Request, model_id: ModelId, body: PredictRequest):
    out = await svc(req).predict(model_id, body.inputs if isinstance(body.inputs, list) else [body.inputs])
    if not out:
        raise HTTPException(404, "Model not found")
    return out


@router.post("/interpret", tags=["ask"], summary="Streamed Claude interpretation of an investigation or the portfolio (requires ANTHROPIC_API_KEY)",
             response_class=StreamingResponse, responses={200: {"content": {"text/plain": {}}}})
async def interpret_route(req: Request, body: InterpretRequest = Body(...)):
    s = svc(req)
    if not s.claude:
        raise HTTPException(503, "Claude is not configured. Set ANTHROPIC_API_KEY and restart the server.")
    ok, retry = req.app.state.limiter.check("claude:" + req.state.rate_key, limit=10)
    if not ok:
        raise HTTPException(429, f"Claude rate limit exceeded; retry in {retry} s")
    return StreamingResponse(interpret.stream(s.claude, s.settings.claude_model, body.model_dump()),
                             media_type="text/plain; charset=utf-8", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
