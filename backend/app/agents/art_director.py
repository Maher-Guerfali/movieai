from app.models.entities import Asset


def make_prompt(asset: Asset, version: int = 1) -> dict:
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
