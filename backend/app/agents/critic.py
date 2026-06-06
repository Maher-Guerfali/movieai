"""Critic — backed by Google Gemini (multimodal).

Reviews a generated image against its brief and the style bible, returns scores,
a verdict, specific issues, and concrete prompt suggestions.
"""

from __future__ import annotations

from app.core.config import settings
from app.models.entities import Asset, Project
from app.providers.base import ProviderError, google_json

CRITIC_SYSTEM = (
    "You are the Critic of an autonomous AI movie studio. You are shown a generated image, "
    "its brief, and the style bible. Judge it strictly. Approve only if it meets the threshold "
    "and has no critical anatomy/artifact problem. Be specific — your notes become the next "
    "prompt iteration."
)


async def review_asset(project: Project, asset: Asset, image_b64: str, mime: str = "image/png") -> dict:
    user = (
        f"Project: {project.name}\nStyle bible: {project.style}\n"
        f"Asset: {asset.name} ({asset.kind.value})\nBrief: {asset.brief or asset.description}\n\n"
        f"Approval thresholds: brief_match >= {settings.approval_min_brief_match}, "
        f"style_consistency >= {settings.approval_min_style}.\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "verdict": "APPROVED|REJECTED",\n'
        '  "scores": {"brief_match": 0, "style_consistency": 0, "character_consistency": 0,\n'
        '             "technical_quality": 0, "anatomy_artifacts": 0},\n'
        '  "issues": ["..."],\n'
        '  "prompt_suggestions": {"add": ["..."], "remove": ["..."], "negative_add": ["..."]},\n'
        '  "notes": "..."\n'
        "}"
    )
    data = await google_json(CRITIC_SYSTEM, user, image_b64=image_b64, mime=mime)
    verdict = str(data.get("verdict", "")).upper()
    if verdict not in {"APPROVED", "REJECTED"}:
        raise ProviderError(f"Critic returned an invalid verdict for {asset.name}: {verdict!r}")
    data["verdict"] = verdict
    data.setdefault("scores", {})
    data.setdefault("issues", [])
    data.setdefault("prompt_suggestions", {})
    data.setdefault("notes", "")
    return data
