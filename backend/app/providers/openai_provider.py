import json
from typing import Any

import httpx

from app.core.config import settings

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider:
    """Real OpenAI (GPT) chat provider using the REST API over httpx."""

    name = "openai"

    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
        if json_schema is not None:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                OPENAI_CHAT_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"].get("content") or ""
        parsed: dict[str, Any] = {}
        if json_schema is not None and content:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {}
        return {"content": content, "json": parsed}

    async def vision(
        self,
        system: str,
        images: list[dict[str, Any]],
        prompt: str,
    ) -> dict[str, Any]:
        image_parts = [
            {"type": "image_url", "image_url": {"url": image["url"]}}
            for image in images
            if image.get("url")
        ]
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}, *image_parts],
            }
        ]
        return await self.complete(system, messages)
