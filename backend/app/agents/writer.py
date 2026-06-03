"""Writer agent.

Generates the screenplay, scene breakdown and asset list (characters,
environments, props) for a movie from the user's idea using GPT. There is no
hardcoded story anymore — everything is produced from the project's instruction.
"""

from app.models.entities import AssetKind
from app.providers.factory import get_provider

WRITER_SYSTEM = """You are the Writer/Producer of an autonomous AI movie studio.
Given a movie idea and a visual style, break it into a production package for an
animated film.

Respond ONLY with JSON of this exact shape:
{
  "title": "<short movie title>",
  "screenplay": "<2-4 paragraph narrative synopsis>",
  "scenes": [
    {"title": "<scene title>", "summary": "<1-2 sentences>", "location": "<place>", "time_of_day": "day|night|dusk|dawn"}
  ],
  "assets": [
    {"kind": "CHARACTER|ENVIRONMENT|PROP", "name": "<name>", "description": "<1 sentence>"}
  ]
}

Rules:
- 6 to 10 scenes.
- 2 to 5 CHARACTER assets, 2 to 5 ENVIRONMENT assets, 1 to 4 PROP assets.
- Keep names concrete and unique. No commentary outside the JSON."""


def brief_for(kind: AssetKind, name: str, description: str, style: str) -> str:
    return (
        f"{name} must read in the film's visual style ({style}). "
        f"Core brief: {description}"
    )


def _fallback_package(idea: str) -> dict:
    """Deterministic package derived from the idea (used only in mock mode).

    This is NOT a hardcoded story — it is generated from whatever idea the user
    typed, so mock mode stays runnable without an API key.
    """
    snippet = idea.strip().rstrip(".")
    title = (snippet[:48] + "…") if len(snippet) > 48 else (snippet or "Untitled Movie")
    beats = ["Opening", "Inciting Incident", "Rising Action", "Midpoint", "Crisis", "Climax", "Resolution"]
    scenes = [
        {"title": f"{beat}", "summary": f"{beat} of: {snippet}.", "location": "Scene location", "time_of_day": "day"}
        for beat in beats
    ]
    assets = [
        {"kind": "CHARACTER", "name": "Protagonist", "description": f"The lead of: {snippet}."},
        {"kind": "CHARACTER", "name": "Antagonist", "description": "The opposing force in the story."},
        {"kind": "ENVIRONMENT", "name": "Primary Setting", "description": "The main world the story unfolds in."},
        {"kind": "ENVIRONMENT", "name": "Secondary Setting", "description": "A contrasting location."},
        {"kind": "PROP", "name": "Key Object", "description": "An object central to the plot."},
    ]
    return {"title": title.title(), "screenplay": f"A film about: {snippet}.", "scenes": scenes, "assets": assets}


async def generate_story(idea: str, style: str) -> tuple[dict, int]:
    """Generate the full story package from the idea. Returns (package, tokens).

    package = {title, screenplay, scenes:[...], assets:[...]}
    With a real provider, raises RuntimeError if nothing usable comes back so
    the caller can surface a clear error. In mock mode, returns a deterministic
    package derived from the idea so the UI stays testable offline.
    """
    provider = get_provider()
    user = f"Movie idea:\n{idea}\n\nVisual style:\n{style}"
    result = await provider.complete(
        WRITER_SYSTEM, [{"role": "user", "content": user}], json_schema={"type": "object"}
    )
    data = result.get("json") or {}
    tokens = int(result.get("tokens", 0))

    scenes = data.get("scenes") or []
    assets = data.get("assets") or []
    if not scenes or not assets:
        if provider.name == "mock":
            return _fallback_package(idea), tokens
        raise RuntimeError(
            "Writer model returned no scenes/assets. "
            f"(provider={provider.name}; check your API key, model name, and quota)"
        )

    # Normalize asset kinds to the enum values.
    normalized_assets = []
    for asset in assets:
        kind = str(asset.get("kind", "PROP")).upper()
        if kind not in {"CHARACTER", "ENVIRONMENT", "PROP"}:
            kind = "PROP"
        normalized_assets.append(
            {
                "kind": kind,
                "name": asset.get("name", "Untitled"),
                "description": asset.get("description", ""),
            }
        )

    return (
        {
            "title": data.get("title", "Untitled Movie"),
            "screenplay": data.get("screenplay", ""),
            "scenes": scenes,
            "assets": normalized_assets,
        },
        tokens,
    )
