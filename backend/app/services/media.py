from pathlib import Path

from app.core.config import settings

MEDIA_ROOT = Path(settings.media_dir)


def ensure_media_dir() -> Path:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    return MEDIA_ROOT


def save_image(image_id: str, data: bytes, ext: str = "png") -> str:
    """Persist image bytes to the media dir, returning the relative key."""
    ensure_media_dir()
    key = f"{image_id}.{ext}"
    (MEDIA_ROOT / key).write_bytes(data)
    return key


def image_path(key: str) -> Path | None:
    path = MEDIA_ROOT / key
    return path if path.exists() else None
