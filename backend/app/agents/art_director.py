from app.models.entities import Asset
from app.providers.factory import get_provider

ART_DIRECTOR_SYSTEM = """You are the Art Director of an AI movie studio producing
"Lili Marleen - Damascus" in a restrained Waltz with Bashir style (rotoscoped-real
anatomy, hand-drawn ink, muted sepia/olive palette, high-contrast hatching,
restrained war-memory tone).

Given an asset (a character, environment, or prop) and its brief, write a single
production reference image prompt. Respond ONLY with JSON:
{
  "positive": "<rich, specific positive prompt in the style bible>",
  "negative": "<things to avoid>"
}"""


def make_prompt(asset: Asset, version: int = 1) -> dict:
    """Deterministic fallback prompt (used in mock mode or on provider failure)."""
    seed = abs(hash((asset.name, version))) % 900000 + 100000
    return {
        "positive": (
            f"{asset.name}, {asset.brief}, cinematic production reference frame, "
            "Waltz with Bashir inspired rotoscoped hand-drawn animation, dusty muted palette, "
            "olive and sepia shadows, etched ink hatching, restrained emotional realism"
        ),
        "negative": (
            "glossy 3d, clean photoreal commercial lighting, superhero pose, plastic skin, "
            "overly saturated colors, melodrama, gore spectacle, broken anatomy"
        ),
        "params": {
            "steps": 28,
            "cfg": 7,
            "sampler": "dpmpp_2m",
            "width": 1024,
            "height": 576,
            "seed_strategy": "asset-stable-versioned",
        },
        "seed": seed,
        "version": version,
    }


async def generate_prompt(asset: Asset, version: int = 1) -> tuple[dict, int]:
    """Generate a prompt via the LLM, returning (prompt_dict, tokens_used).

    Falls back to the deterministic template if the provider fails or returns
    nothing usable.
    """
    base = make_prompt(asset, version)
    provider = get_provider()
    user = (
        f"Asset name: {asset.name}\n"
        f"Kind: {asset.kind.value}\n"
        f"Description: {asset.description}\n"
        f"Brief: {asset.brief}"
    )
    try:
        result = await provider.complete(
            ART_DIRECTOR_SYSTEM, [{"role": "user", "content": user}], json_schema={"type": "object"}
        )
    except Exception:  # noqa: BLE001
        return base, 0

    data = result.get("json") or {}
    if data.get("positive"):
        base["positive"] = data["positive"]
    if data.get("negative"):
        base["negative"] = data["negative"]
    return base, int(result.get("tokens", 0))
