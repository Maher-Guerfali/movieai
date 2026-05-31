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


class MockProvider:
    name = "mock"

    async def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"content": "Mock completion: provider keys are not configured.", "json": {}}

    async def vision(
        self,
        system: str,
        images: list[dict[str, Any]],
        prompt: str,
    ) -> dict[str, Any]:
        return {"content": "Mock vision review.", "json": {}}
