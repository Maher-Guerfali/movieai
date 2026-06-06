"""ComfyUI client — real txt2img generation.

Loads a workflow graph template, injects the prompt/params, submits it, polls
history until the image is produced, and exposes a way to fetch the resulting
image bytes. Requires a reachable ComfyUI with a valid workflow graph; there is
no mock path.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.providers.base import ProviderError

WORKFLOWS_DIR = Path(__file__).resolve().parent / "workflows"


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

    def _load_workflow(self, prompt: dict[str, Any]) -> dict[str, Any]:
        path = WORKFLOWS_DIR / f"{settings.comfy_workflow}.json"
        if not path.exists():
            raise ProviderError(f"ComfyUI workflow '{settings.comfy_workflow}' not found at {path}.")
        graph = json.loads(path.read_text(encoding="utf-8"))
        # A real ComfyUI API-format graph is a node map keyed by id where each
        # value has a "class_type". The shipped template is a placeholder, so we
        # require the operator to install a real graph before generating.
        is_real_graph = isinstance(graph, dict) and any(
            isinstance(node, dict) and "class_type" in node for node in graph.values()
        )
        if not is_real_graph:
            raise ProviderError(
                "The ComfyUI workflow is a placeholder. Replace "
                f"{path} with a real exported API-format graph that uses the tokens "
                "%positive%, %negative%, %seed%, %steps%, %cfg%, %width%, %height%."
            )
        params = prompt.get("params", {})
        replacements = {
            "%positive%": prompt.get("positive", ""),
            "%negative%": prompt.get("negative", ""),
            "%seed%": prompt.get("seed", 0),
            "%steps%": params.get("steps", 28),
            "%cfg%": params.get("cfg", 7),
            "%width%": params.get("width", 1024),
            "%height%": params.get("height", 576),
        }
        raw = json.dumps(graph)
        for token, value in replacements.items():
            raw = raw.replace(token, str(value))
        return json.loads(raw)

    async def generate(self, prompt: dict[str, Any]) -> dict[str, Any]:
        """Submit a generation and return {filename, subfolder, type} for the image."""
        graph = self._load_workflow(prompt)
        async with httpx.AsyncClient(timeout=settings.comfy_timeout_s) as client:
            submit = await client.post(f"{self.base_url}/prompt", json={"prompt": graph})
            if not submit.is_success:
                raise ProviderError(f"ComfyUI submit failed {submit.status_code}: {submit.text[:200]}")
            prompt_id = submit.json()["prompt_id"]

            remaining = settings.comfy_timeout_s
            while remaining > 0:
                history = await client.get(f"{self.base_url}/history/{prompt_id}")
                if history.is_success and prompt_id in history.json():
                    outputs = history.json()[prompt_id].get("outputs", {})
                    for node in outputs.values():
                        for image in node.get("images", []):
                            return {
                                "filename": image["filename"],
                                "subfolder": image.get("subfolder", ""),
                                "type": image.get("type", "output"),
                                "prompt_id": prompt_id,
                            }
                await asyncio.sleep(1.5)
                remaining -= 1.5
        raise ProviderError(f"ComfyUI generation timed out for prompt {prompt_id}.")

    async def fetch_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        async with httpx.AsyncClient(timeout=settings.comfy_timeout_s) as client:
            response = await client.get(f"{self.base_url}/view", params=params)
            if not response.is_success:
                raise ProviderError(f"ComfyUI view failed {response.status_code}.")
            return response.content


comfy = ComfyUIClient()
