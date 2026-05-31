from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.art_director import make_prompt
from app.agents.critic import review_asset
from app.agents.writer import SEED_ASSETS, SEED_SCENES, brief_for, screenplay_excerpt
from app.events.bus import emit
from app.models.entities import (
    Asset,
    AssetKind,
    AssetState,
    Event,
    Image,
    Project,
    ProjectStatus,
    Prompt,
    Review,
    Scene,
    Task,
    TaskStatus,
)


async def ensure_seed_project(db: Session, project: Project) -> None:
    if db.scalar(select(Scene).where(Scene.project_id == project.id)):
        return

    project.roadmap = {
        "screenplay": screenplay_excerpt(),
        "milestone": "M2 seed tree generated; M3/M4 mocked image and review loop ready.",
        "next": ["Replace mock provider calls with live GPT/Claude/Gemini adapters", "Connect real ComfyUI workflow"],
    }

    for index, (slug, title, summary, location) in enumerate(SEED_SCENES, start=1):
        db.add(
            Scene(
                project_id=project.id,
                act_no=index,
                scene_no=index,
                slug=slug,
                title=title,
                summary=summary,
                location=location,
                time_of_day="night" if index in {1, 3, 9} else "day",
                shots=[
                    {"shot_no": 1, "description": f"Establish {location} with restrained inked realism.", "camera": "wide", "duration_s": 8},
                    {"shot_no": 2, "description": f"Hold on the emotional consequence of {title.lower()}.", "camera": "medium", "duration_s": 12},
                ],
            )
        )

    for kind, name, description in SEED_ASSETS:
        db.add(
            Asset(
                project_id=project.id,
                kind=kind,
                name=name,
                description=description,
                brief=brief_for(kind, name, description),
                state=AssetState.PLANNING,
                metadata_json={"related_scenes": [], "source": "seed/story.md"},
            )
        )

    db.commit()
    await emit(db, project.id, "project.seeded", "writer", {"message": "Seed story analyzed into scenes and assets."})


async def run_seed_tick(db: Session, project: Project) -> None:
    await ensure_seed_project(db, project)

    assets = db.scalars(select(Asset).where(Asset.project_id == project.id)).all()
    if not db.scalar(select(Task).where(Task.project_id == project.id)):
        task_defs = [
            ("story.analyze", "writer", "Analyze seed story into screenplay and scene breakdown"),
            ("assets.brief", "writer", "Create environment, character, and prop bibles"),
            ("prompts.generate", "art_director", "Generate production prompts for seed assets"),
            ("images.generate", "art_director", "Create mock ComfyUI references for seed assets"),
            ("images.review", "critic", "Review references against brief and style bible"),
        ]
        for priority, (task_type, owner, label) in enumerate(task_defs, start=1):
            db.add(
                Task(
                    project_id=project.id,
                    type=task_type,
                    owner_agent=owner,
                    status=TaskStatus.TODO,
                    priority=priority * 10,
                    payload={"label": label},
                )
            )
        db.commit()

    for task in db.scalars(select(Task).where(Task.project_id == project.id).order_by(Task.priority)).all():
        if task.status == TaskStatus.DONE:
            continue
        task.status = TaskStatus.IN_PROGRESS
        db.commit()
        await emit(db, project.id, "task.started", task.owner_agent, {"task_id": task.id, "label": task.payload.get("label")})
        task.status = TaskStatus.DONE
        db.commit()
        await emit(db, project.id, "task.completed", task.owner_agent, {"task_id": task.id, "label": task.payload.get("label")})

    for asset in assets:
        if not asset.prompts:
            prompt_data = make_prompt(asset)
            prompt = Prompt(asset_id=asset.id, agent="art_director", **prompt_data)
            db.add(prompt)
            asset.state = AssetState.GENERATING
            db.commit()
            db.refresh(prompt)
            await emit(db, project.id, "prompt.created", "art_director", {"asset_id": asset.id, "prompt_id": prompt.id})
            await emit(db, project.id, "generation.queued", "art_director", {"asset_id": asset.id, "prompt_id": prompt.id})
        else:
            prompt = asset.prompts[0]

        if not asset.images:
            image = Image(
                asset_id=asset.id,
                prompt_id=prompt.id,
                minio_key=f"mock/{asset.id}.svg",
                width=1024,
                height=576,
                seed=prompt.seed,
                state=AssetState.UNDER_REVIEW,
                meta={"mock": True, "palette": "sepia/olive/ink"},
            )
            db.add(image)
            asset.state = AssetState.UNDER_REVIEW
            db.commit()
            db.refresh(image)
            await emit(db, project.id, "image.created", "asset_manager", {"asset_id": asset.id, "image_id": image.id, "url": f"/api/images/{image.id}"})
        else:
            image = asset.images[0]

        if not asset.reviews:
            review_data = review_asset(asset)
            verdict = review_data["verdict"]
            db.add(Review(asset_id=asset.id, image_id=image.id, critic_agent="critic", **review_data))
            asset.state = AssetState.APPROVED if verdict == "APPROVED" else AssetState.REJECTED
            image.state = asset.state
            db.commit()
            await emit(db, project.id, "review.completed", "critic", {"asset_id": asset.id, "image_id": image.id, "verdict": verdict, "scores": review_data["scores"]})
            await emit(db, project.id, "asset.state_changed", "asset_manager", {"asset_id": asset.id, "to": asset.state.value})


def project_counts(db: Session, project_id: str) -> dict[str, int]:
    return {
        "scenes": len(db.scalars(select(Scene).where(Scene.project_id == project_id)).all()),
        "environments": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.ENVIRONMENT)).all()),
        "characters": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.CHARACTER)).all()),
        "props": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.PROP)).all()),
        "tasks": len(db.scalars(select(Task).where(Task.project_id == project_id)).all()),
        "notifications": len(db.scalars(select(Event).where(Event.project_id == project_id, Event.read.is_(False))).all()),
    }


async def start_project(db: Session, project: Project) -> Project:
    project.status = ProjectStatus.RUNNING
    db.commit()
    await emit(db, project.id, "project.started", "producer", {"status": "RUNNING"})
    await run_seed_tick(db, project)
    return project
