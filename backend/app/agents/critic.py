from app.models.entities import Asset


def review_asset(asset: Asset) -> dict:
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
