from typing import Any, Protocol


class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    async def vision(
        self,
        system: str,
        images: list[dict[str, Any]],
        prompt: str,
    ) -> dict[str, Any]:
        ...

    async def image(self, prompt: str, size: str | None = None) -> bytes:
        ...


class MockProvider:
    name = "mock"

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "content": "Mock completion: provider keys are not configured.",
            "json": {},
            "tokens": 0,
        }

    async def vision(
        self,
        system: str,
        images: list[dict[str, Any]],
        prompt: str,
    ) -> dict[str, Any]:
        return {"content": "Mock vision review.", "json": {}, "tokens": 0}

    async def image(self, prompt: str, size: str | None = None) -> bytes:
        # 1x1 transparent PNG so callers always get valid bytes in mock mode.
        import base64

        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
