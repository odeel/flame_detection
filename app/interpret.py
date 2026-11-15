"""
Streamed Claude interpretations for the dashboard (POST /api/v1/interpret).
Enabled when ANTHROPIC_API_KEY is set; the key never leaves the server.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import anthropic

log = logging.getLogger("fif.interpret")

SYSTEM_PROMPT = """You are a spacecraft fire safety analyst supporting mission designers who build habitable crew environments (ISS, Gateway, Artemis landers and surface habitats) and engineers who apply that research to fire safety on Earth.

You receive structured records of microgravity combustion investigations, many with official NASA Physical Sciences Informatics (PSI) metadata, together with scores from a local ranking engine for four objectives:
1. habitat: relevance to fire safety needs of habitable crew environments
2. modeling: value of the data for predictive modeling of flammability and fire scenarios
3. equipment: value for developing next-generation fire safety controls and equipment (detection, suppression, cleanup)
4. earth: potential applications of the data to fire safety on Earth

You may also receive summaries of machine-learning models trained on PSI test matrices, with cross-validated metrics. Report their skill honestly and never overstate it.

The user's priority weights for these objectives are included. Weight your emphasis accordingly.

Ground every statement in the supplied records. When you draw on general combustion knowledge beyond them, say so. Values marked as measured come from PSI test matrices; others are approximate envelopes. If an implication is uncertain, say so plainly. Do not invent numbers, dates or results.

Write in plain prose with short headed sections. Keep it under about 550 words. Use these sections:
- Bottom line (2-3 sentences)
- What it tells us about fire in crewed spacecraft
- Data for predictive models (which parameters and ranges are usable, and what is missing)
- Implications for controls and equipment
- Applications to fire safety on Earth (which domains, why the physics transfers, and what 1-g validation is needed)
- Open questions and recommended next tests"""


def user_message(body: dict) -> str:
    weights = json.dumps(body.get("weights") or {})
    if body.get("mode") == "portfolio":
        return (f"Priority weights: {weights}\n\nRanked investigation portfolio (engine output):\n{json.dumps(body.get('ranked') or [], indent=1)}\n\n"
                f"Coverage of reference cabin atmospheres:\n{json.dumps(body.get('coverage') or [], indent=1)}\n\n"
                + (f"Trained models (cross-validated):\n{json.dumps(body['models'], indent=1)}\n\n" if body.get("models") else "")
                + "Write a portfolio-level synthesis for a habitat fire safety review. In addition to the standard sections, name the five investigations "
                  "that matter most for these priorities and say why, point out the most important evidence gaps, and identify the most promising Earth fire-safety spin-offs.")
    return (f"Priority weights: {weights}\n\nInvestigation record:\n{json.dumps(body.get('investigation') or {}, indent=1)}\n\n"
            f"Engine scores and extracted parameters:\n{json.dumps(body.get('engine') or {}, indent=1)}\n\n"
            "Interpret this investigation for spacecraft fire safety and for Earth applications.")


async def stream(client, model: str, body: dict) -> AsyncIterator[str]:
    """Yield text chunks; errors are reported inline so a half-written answer is never silently cut."""
    try:
        async with client.beta.messages.stream(
            model=model, max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            thinking={"type": "adaptive"}, output_config={"effort": "medium"},
            system=SYSTEM_PROMPT, messages=[{"role": "user", "content": user_message(body)}],
        ) as s:
            async for text in s.text_stream:
                yield text
            final = await s.get_final_message()
        if final.stop_reason == "refusal":
            yield "\n\n[The model declined this request]"
        elif final.stop_reason == "max_tokens":
            yield "\n\n[Output truncated at the token limit]"
    except anthropic.AuthenticationError:
        yield "\n[Claude request failed: authentication failed; check ANTHROPIC_API_KEY]"
    except anthropic.RateLimitError:
        yield "\n[Claude request failed: rate limited; try again shortly]"
    except anthropic.APIError as e:
        log.warning("interpret failed: %s", e)
        yield f"\n[Claude request failed: API error {getattr(e, 'status_code', '')}: {e.message}]"
