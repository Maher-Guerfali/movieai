import httpx

from app.core.config import settings


class ComfyUIClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.comfyui_url).rstrip("/")

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.base_url}/system_stats")
            return {"available": response.is_success, "status_code": response.status_code}
        except httpx.HTTPError:
            return {"available": False, "status_code": None}

    async def submit_txt2img(self, prompt: dict) -> str:
        if settings.use_mock_ai:
            return f"mock-{prompt['seed']}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}/prompt", json=prompt)
            response.raise_for_status()
            return response.json()["prompt_id"]
