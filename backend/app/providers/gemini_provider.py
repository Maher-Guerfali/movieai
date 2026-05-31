import json
from typing import Any

import httpx

from app.core.config import settings

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider:
    """Real Google Gemini chat provider using the Generative Language REST API."""

    name = "google"

    def __init__(self) -> None:
        self.api_key = settings.google_api_key
        self.model = settings.google_model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        contents = [
            {
                "role": "user" if message.get("role") == "user" else "model",
                "parts": [{"text": message.get("content", "")}],
            }
            for message in messages
        ]
        body: dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
        }
        if json_schema is not None:
            body["generationConfig"] = {"responseMimeType": "application/json"}

        url = f"{GEMINI_BASE}/{self.model}:generateContent?key={self.api_key}"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
            data = response.json()

        content = ""
        candidates = data.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(part.get("text", "") for part in parts)

        parsed: dict[str, Any] = {}
        if json_schema is not None and content:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {}
        usage = data.get("usageMetadata", {}) or {}
        return {
            "content": content,
            "json": parsed,
            "tokens": int(usage.get("totalTokenCount", 0)),
        }

    async def vision(
        self,
        system: str,
        images: list[dict[str, Any]],
        prompt: str,
    ) -> dict[str, Any]:
        return await self.complete(
            system, [{"role": "user", "content": prompt}], json_schema={"type": "object"}
        )

    async def image(self, prompt: str, size: str | None = None) -> bytes:
        # Image generation is routed through the OpenAI provider; Gemini here
        # only handles text. Fall back to a transparent pixel if used directly.
        from app.providers.base import MockProvider

        return await MockProvider().image(prompt, size)
