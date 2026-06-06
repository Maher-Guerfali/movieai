"""Real LLM provider adapters.

There is no mock fallback: a phase that needs a model will raise
``ProviderError`` if the relevant key is not configured. The orchestrator
turns that into a FAILED phase + ``needs_director`` event so the UI can show
exactly what is missing instead of silently faking output.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import settings


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured or returns an error."""


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort parse of a JSON object out of an LLM text response."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ProviderError(f"Model did not return valid JSON: {exc}") from exc
        raise ProviderError("Model did not return valid JSON.")


async def openai_json(system: str, user: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise ProviderError("OPENAI_API_KEY is not configured. Add it to .env to run this phase.")
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        response = await client.post(
            f"{settings.openai_base_url}/chat/completions", json=payload, headers=headers
        )
    if not response.is_success:
        raise ProviderError(f"OpenAI error {response.status_code}: {response.text[:300]}")
    content = response.json()["choices"][0]["message"]["content"]
    return _extract_json(content)


async def anthropic_json(system: str, user: str) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise ProviderError("ANTHROPIC_API_KEY is not configured. Add it to .env to run this phase.")
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": settings.llm_max_tokens,
        "system": system + "\n\nRespond with a single valid JSON object and nothing else.",
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        response = await client.post(
            f"{settings.anthropic_base_url}/messages", json=payload, headers=headers
        )
    if not response.is_success:
        raise ProviderError(f"Anthropic error {response.status_code}: {response.text[:300]}")
    blocks = response.json().get("content", [])
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    return _extract_json(text)


async def google_json(system: str, user: str, image_b64: str | None = None, mime: str = "image/png") -> dict[str, Any]:
    if not settings.google_api_key:
        raise ProviderError("GOOGLE_API_KEY is not configured. Add it to .env to run this phase.")
    parts: list[dict[str, Any]] = [{"text": user}]
    if image_b64:
        parts.append({"inline_data": {"mime_type": mime, "data": image_b64}})
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    url = (
        f"{settings.google_base_url}/models/{settings.google_model}:generateContent"
        f"?key={settings.google_api_key}"
    )
    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        response = await client.post(url, json=payload)
    if not response.is_success:
        raise ProviderError(f"Google error {response.status_code}: {response.text[:300]}")
    candidates = response.json().get("candidates", [])
    if not candidates:
        raise ProviderError("Google returned no candidates.")
    text = "".join(part.get("text", "") for part in candidates[0]["content"]["parts"])
    return _extract_json(text)
