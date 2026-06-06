"""Writer / Story Architect — backed by Anthropic Claude.

Reads the seed source material and produces the screenplay, scene breakdown,
and the list of assets (environments, characters, props) to build. Also writes
the per-asset creative brief. No hardcoded story content lives here anymore.
"""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Asset, AssetKind, Project
from app.providers.base import ProviderError, anthropic_json

SEED_DIR = Path(__file__).resolve().parents[3] / "seed"

WRITER_SYSTEM = (
    "You are the Screenwriter and Story Architect of an autonomous AI movie studio. "
    "Analyze the source story and produce a screenplay summary, a scene breakdown, and "
    "the list of visual assets to build. For each character, environment, and prop you "
    "name, you will later write a tight creative brief, but do NOT write image prompts. "
    "Maintain continuity and respect the project's style bible."
)


def _read_seed() -> str:
    parts: list[str] = []
    for name in ("story.md", "character_bible.md", "story-source.txt"):
        path = SEED_DIR / name
        if path.exists():
            parts.append(f"# FILE: {name}\n{path.read_text(encoding='utf-8')}")
    if not parts:
        raise ProviderError(f"No seed source material found in {SEED_DIR}.")
    return "\n\n".join(parts)


async def analyze_story(project: Project) -> dict:
    """Return {screenplay, scenes:[...], assets:[...]} derived from the seed."""
    source = _read_seed()
    user = (
        f"Project title: {project.name}\n"
        f"Style bible: {project.style}\n"
        f"Director instruction: {project.instruction or 'Adapt the source faithfully.'}\n\n"
        "Source material:\n"
        f"{source}\n\n"
        "Return JSON with this exact shape:\n"
        "{\n"
        '  "screenplay": "3-6 sentence prose summary of the screenplay arc",\n'
        '  "scenes": [{"act_no": 1, "scene_no": 1, "slug": "kebab-case", "title": "...",\n'
        '              "summary": "...", "location": "...", "time_of_day": "day|night|dusk",\n'
        '              "shots": [{"shot_no": 1, "description": "...", "camera": "wide|medium|close", "duration_s": 8}]}],\n'
        '  "assets": [{"kind": "ENVIRONMENT|CHARACTER|PROP", "name": "...", "description": "..."}]\n'
        "}\n"
        "Cover every chapter as at least one scene and every key place/character/prop as an asset."
    )
    data = await anthropic_json(WRITER_SYSTEM, user)
    if not data.get("scenes") or not data.get("assets"):
        raise ProviderError("Writer returned no scenes or assets.")
    return data


async def write_brief(project: Project, asset: Asset) -> str:
    user = (
        f"Project: {project.name}\nStyle bible: {project.style}\n"
        f"Asset kind: {asset.kind.value}\nName: {asset.name}\nDescription: {asset.description}\n\n"
        "Write the creative brief for this asset: what it must convey on screen, mood, period, "
        "key visual notes, and continuity constraints — enough for an Art Director to write an "
        "image prompt. Return JSON: {\"brief\": \"...\"}"
    )
    data = await anthropic_json(WRITER_SYSTEM, user)
    brief = data.get("brief", "").strip()
    if not brief:
        raise ProviderError(f"Writer returned an empty brief for {asset.name}.")
    return brief
