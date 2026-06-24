"""AI ticket analysis — extract flight segments from boarding-pass images.

Provider-switchable. Defaults to Google **Gemini** (called over its REST API via
httpx — no heavy SDK, works everywhere incl. Render). Falls back to Anthropic
Claude if only ANTHROPIC_API_KEY is set. Set LLM_PROVIDER=gemini|anthropic to
force one.

We DO NOT store the raw image — only the extracted data — keeping the privacy
profile aligned with "country only".

A flight on date D from country A to country B is a TRAVEL DAY: when committed,
date D is credited to BOTH A and B, which the counting engine treats as a
travel day.

Env:
  GEMINI_API_KEY / GEMINI_MODEL (default gemini-2.5-flash)
  ANTHROPIC_API_KEY / ANTHROPIC_MODEL (default claude-opus-4-8)
  LLM_PROVIDER (optional: "gemini" | "anthropic")
"""
from __future__ import annotations

import base64
import json
import os
from typing import Dict, List

import httpx

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

# Exact JSON shape we ask the model to return (one object, "segments" array).
PROMPT = (
    "You are extracting flight information from a boarding pass or flight ticket image. "
    "Return ONLY valid JSON, no markdown, in exactly this shape:\n"
    '{"segments": [{"date": "YYYY-MM-DD or null", "from_airport": "", "to_airport": "", '
    '"from_country": "IN|AE|OTHER", "to_country": "IN|AE|OTHER", "airline": "", '
    '"flight_no": "", "dep_time": "HH:MM or null", "arr_time": "HH:MM or null", '
    '"confidence": 0.0}]}\n'
    "Rules: include every flight segment shown. Use the year only if printed or unambiguous, "
    "else set date to null. dep_time/arr_time are local 24-hour times (HH:MM) of departure "
    "and arrival as printed; null if not shown. Country codes: India=IN, UAE/Dubai/Abu Dhabi/"
    "Sharjah=AE, else OTHER. "
    "confidence is 0..1. If the image is not a flight ticket, return {\"segments\": []}."
)


class TicketAnalysisError(RuntimeError):
    pass


def _provider() -> str:
    forced = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if forced in ("gemini", "anthropic"):
        return forced
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise TicketAnalysisError(
        "No AI key set — set GEMINI_API_KEY (or ANTHROPIC_API_KEY) for ticket analysis."
    )


def _parse_segments(text: str) -> List[Dict]:
    text = text.strip()
    # Strip ```json fences if the model added them.
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{") :] if "{" in text else text
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TicketAnalysisError("Model returned non-JSON output.") from exc
    segs = data.get("segments", []) if isinstance(data, dict) else []
    return segs if isinstance(segs, list) else []


def _analyze_gemini(image_bytes: bytes, media_type: str) -> List[Dict]:
    api_key = os.environ["GEMINI_API_KEY"]
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    body = {
        "contents": [
            {
                "parts": [
                    {"inline_data": {"mime_type": media_type, "data": b64}},
                    {"text": PROMPT},
                ]
            }
        ],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    resp = httpx.post(
        url, headers={"x-goog-api-key": api_key}, json=body, timeout=60.0
    )
    if resp.status_code != 200:
        raise TicketAnalysisError(f"Gemini API {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return []
    return _parse_segments(text)


def _analyze_anthropic(image_bytes: bytes, media_type: str) -> List[Dict]:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise TicketAnalysisError("The 'anthropic' package is not installed.") from exc
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    return _parse_segments(text) if text else []


def analyze_ticket_image(image_bytes: bytes, media_type: str) -> List[Dict]:
    """Send one image to the configured vision model; return flight segments."""
    provider = _provider()
    if provider == "gemini":
        return _analyze_gemini(image_bytes, media_type)
    return _analyze_anthropic(image_bytes, media_type)
