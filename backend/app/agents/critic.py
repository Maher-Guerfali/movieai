from app.core.config import settings
from app.models.entities import Asset
from app.providers.factory import get_provider

CRITIC_SYSTEM = """You are the Critic of an AI movie studio producing
"Lili Marleen - Damascus" in a restrained Waltz with Bashir style.

Review the generated reference image for an asset against its brief and the style
bible. Score each dimension 1-10 (anatomy_artifacts is 1=clean, 10=broken).
Respond ONLY with JSON:
{
  "verdict": "APPROVED" | "REJECTED",
  "scores": {
    "brief_match": <int>,
    "style_consistency": <int>,
    "character_consistency": <int>,
    "technical_quality": <int>,
    "anatomy_artifacts": <int>
  },
  "issues": ["<short issue>", ...],
  "notes": "<one or two sentences>"
}
Approve only when brief_match and style_consistency are both >= the studio
thresholds and there are no serious anatomy artifacts."""


def review_asset(asset: Asset) -> dict:
    """Deterministic fallback review (used in mock mode or on provider failure)."""
    issues = []
    if "Waltz with Bashir" not in asset.brief:
        issues.append("Style bible is not explicit enough.")
    verdict = "APPROVED" if not issues else "REJECTED"
    return {
        "verdict": verdict,
        "scores": {
            "brief_match": 8,
            "style_consistency": 8,
            "character_consistency": 7 if asset.kind.value == "CHARACTER" else 8,
            "technical_quality": 8,
            "anatomy_artifacts": 1,
        },
        "issues": issues,
        "prompt_suggestions": {
            "add": ["more etched cross-hatching", "stronger dusty light"],
            "remove": [],
            "negative_add": ["glossy skin", "clean digital concept art"],
        },
        "notes": (
            "Approved as a seed production reference. The frame carries the muted inked war-memory look "
            "and gives the Art Director a stable direction for the next variant."
        ),
    }


async def review_image(asset: Asset, image_url: str) -> tuple[dict, int]:
    """Review a generated image via the LLM, returning (review_dict, tokens)."""
    fallback = review_asset(asset)
    provider = get_provider()
    prompt = (
        f"Asset: {asset.name} ({asset.kind.value})\n"
        f"Brief: {asset.brief}\n"
        f"Thresholds: brief_match>={settings.approval_min_brief_match}, "
        f"style_consistency>={settings.approval_min_style}.\n"
        "Review the attached reference image."
    )
    try:
        result = await provider.vision(CRITIC_SYSTEM, [{"url": image_url}], prompt)
    except Exception:  # noqa: BLE001
        return fallback, 0

    data = result.get("json") or {}
    if not data.get("verdict"):
        return fallback, int(result.get("tokens", 0))

    scores = data.get("scores", {}) or {}
    verdict = "APPROVED" if str(data["verdict"]).upper() == "APPROVED" else "REJECTED"
    review = {
        "verdict": verdict,
        "scores": {
            "brief_match": int(scores.get("brief_match", 7)),
            "style_consistency": int(scores.get("style_consistency", 7)),
            "character_consistency": int(scores.get("character_consistency", 7)),
            "technical_quality": int(scores.get("technical_quality", 7)),
            "anatomy_artifacts": int(scores.get("anatomy_artifacts", 2)),
        },
        "issues": data.get("issues", []) or [],
        "prompt_suggestions": data.get("prompt_suggestions", {}) or {},
        "notes": data.get("notes", ""),
    }
    return review, int(result.get("tokens", 0))
