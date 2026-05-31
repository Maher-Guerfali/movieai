from app.models.entities import Asset, Image, Project
from app.orchestrator.service import project_counts
from app.schemas.api import AssetOut, ImageOut, ProjectOut, PromptOut, ReviewOut


def image_url(image: Image) -> str:
    return f"/api/images/{image.id}"


def to_asset_out(asset: Asset) -> AssetOut:
    return AssetOut(
        id=asset.id,
        project_id=asset.project_id,
        kind=asset.kind,
        name=asset.name,
        description=asset.description,
        brief=asset.brief,
        state=asset.state,
        metadata_json=asset.metadata_json,
        prompts=[PromptOut.model_validate(prompt) for prompt in asset.prompts],
        images=[
            ImageOut(
                id=image.id,
                minio_key=image.minio_key,
                width=image.width,
                height=image.height,
                seed=image.seed,
                state=image.state,
                meta=image.meta,
                url=image_url(image),
            )
            for image in asset.images
        ],
        reviews=[ReviewOut.model_validate(review) for review in asset.reviews],
    )


def to_project_out(db, project: Project) -> ProjectOut:
    payload = ProjectOut.model_validate(project)
    payload.counts = project_counts(db, project.id)
    return payload
