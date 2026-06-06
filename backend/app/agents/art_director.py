"""Art Director — backed by OpenAI GPT.

Turns a creative brief into a production-ready image prompt for the project's
style bible. When the Critic rejects an image, it reads the prompt_suggestions
and produces the next iteration.
"""

from __future__ import annotations

from app.models.entities import Asset, Project, Review
from app.providers.base import ProviderError, openai_json

ART_DIRECTOR_SYSTEM = (
    "You are the Art Director of an autonomous AI movie studio. Convert a creative brief "
    "into a production-ready image prompt for the project's style bible. Produce a positive "
    "prompt, a negative prompt, and generation parameters. Reuse motifs and seeds from prior "
    "approved references of the same subject to keep consistency. When given critic notes for "
    "a rejected image, change only what the notes call for."
)


async def make_prompt(project: Project, asset: Asset, version: int = 1, critic: Review | None = None) -> dict:
    notes = ""
    if critic is not None:
        notes = (
            "\nThe previous version was REJECTED. Critic issues: "
            f"{critic.issues}. Suggestions: {critic.prompt_suggestions}. "
            "Produce the next iteration addressing only these."
        )
    user = (
        f"Project: {project.name}\nStyle bible: {project.style}\n"
        f"Asset: {asset.name} ({asset.kind.value})\nBrief: {asset.brief or asset.description}\n"
        f"Iteration version: {version}.{notes}\n\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "positive": "comma-separated production prompt",\n'
        '  "negative": "things to avoid",\n'
        '  "params": {"steps": 28, "cfg": 7, "sampler": "dpmpp_2m", "width": 1024, "height": 576,\n'
        '             "seed": 123456, "seed_strategy": "asset-stable-versioned"},\n'
        '  "version": ' + str(version) + "\n"
        "}"
    )
    data = await openai_json(ART_DIRECTOR_SYSTEM, user)
    if not data.get("positive"):
        raise ProviderError(f"Art Director returned an empty prompt for {asset.name}.")
    params = data.get("params") or {}
    seed = int(params.get("seed") or (abs(hash((asset.name, version))) % 900000 + 100000))
    return {
        "positive": data["positive"],
        "negative": data.get("negative", ""),
        "params": params,
        "seed": seed,
        "version": int(data.get("version", version)),
    }
