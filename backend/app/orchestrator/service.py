import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.art_director import generate_prompt, make_prompt
from app.agents.critic import review_asset, review_image
from app.agents.writer import SEED_ASSETS, SEED_SCENES, brief_for, screenplay_excerpt
from app.core.config import settings
from app.db.session import SessionLocal
from app.events.bus import emit
from app.providers.factory import get_image_provider
from app.services.media import save_image
from app.services.usage import budget_exceeded, record_usage
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
        "milestone": "Seed tree generated; live GPT prompts + OpenAI image generation + GPT review.",
        "next": ["Storyboards", "Animation", "Audio", "Timeline assembly"],
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


def _ensure_tasks(db: Session, project: Project) -> None:
    if db.scalar(select(Task).where(Task.project_id == project.id)):
        return
    task_defs = [
        ("story.analyze", "writer", "Analyze seed story into screenplay and scene breakdown"),
        ("assets.brief", "writer", "Create environment, character, and prop bibles"),
        ("prompts.generate", "art_director", "Generate production prompts for seed assets"),
        ("images.generate", "art_director", "Generate reference images for seed assets"),
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


async def _process_asset(db: Session, project: Project, asset: Asset) -> bool:
    """Advance one asset by one step. Returns True if work was done."""
    # 1. Prompt (GPT-written)
    if not asset.prompts:
        prompt_data, tokens = await generate_prompt(asset)
        record_usage(db, project.id, tokens=tokens)
        prompt = Prompt(asset_id=asset.id, agent="art_director", **prompt_data)
        db.add(prompt)
        asset.state = AssetState.GENERATING
        db.commit()
        db.refresh(prompt)
        await emit(db, project.id, "prompt.created", "art_director", {"asset_id": asset.id, "prompt_id": prompt.id})
        await emit(db, project.id, "generation.queued", "art_director", {"asset_id": asset.id, "prompt_id": prompt.id})
        return True

    prompt = asset.prompts[0]

    # 2. Image (OpenAI images API -> saved to disk)
    if not asset.images:
        image = Image(
            asset_id=asset.id,
            prompt_id=prompt.id,
            minio_key="",
            width=1024,
            height=576,
            seed=prompt.seed,
            state=AssetState.GENERATING,
            meta={},
        )
        db.add(image)
        db.commit()
        db.refresh(image)

        provider = get_image_provider()
        try:
            data = await provider.image(prompt.positive)
            key = save_image(image.id, data)
            image.minio_key = key
            image.meta = {"provider": provider.name, "size": settings.image_size}
            record_usage(db, project.id, images=1)
        except Exception as exc:  # noqa: BLE001
            image.meta = {"error": str(exc), "provider": provider.name}
            await emit(db, project.id, "generation.failed", "art_director", {"asset_id": asset.id, "error": str(exc)})
        image.state = AssetState.UNDER_REVIEW
        asset.state = AssetState.UNDER_REVIEW
        db.commit()
        await emit(db, project.id, "image.created", "asset_manager", {"asset_id": asset.id, "image_id": image.id, "url": f"/api/images/{image.id}"})
        return True

    image = asset.images[0]

    # 3. Review (GPT vision)
    if not asset.reviews:
        review_data, tokens = await review_image(asset, f"/api/images/{image.id}")
        record_usage(db, project.id, tokens=tokens)
        verdict = review_data["verdict"]
        db.add(Review(asset_id=asset.id, image_id=image.id, critic_agent="critic", **review_data))
        asset.state = AssetState.APPROVED if verdict == "APPROVED" else AssetState.REJECTED
        image.state = asset.state
        db.commit()
        await emit(db, project.id, "review.completed", "critic", {"asset_id": asset.id, "image_id": image.id, "verdict": verdict, "scores": review_data["scores"]})
        await emit(db, project.id, "asset.state_changed", "asset_manager", {"asset_id": asset.id, "to": asset.state.value})
        return True

    return False


async def run_seed_tick(db: Session, project: Project) -> bool:
    """Run one unit of production work. Returns True if something was done."""
    await ensure_seed_project(db, project)
    _ensure_tasks(db, project)

    if budget_exceeded(db, project.id):
        await emit(db, project.id, "budget.exhausted", "producer", {"message": "Daily budget reached."})
        project.status = ProjectStatus.PAUSED
        db.commit()
        return False

    # Mark pending tasks as done as their corresponding work progresses.
    for task in db.scalars(select(Task).where(Task.project_id == project.id).order_by(Task.priority)).all():
        if task.status != TaskStatus.DONE:
            task.status = TaskStatus.IN_PROGRESS
            db.commit()
            await emit(db, project.id, "task.started", task.owner_agent, {"task_id": task.id, "label": task.payload.get("label")})
            task.status = TaskStatus.DONE
            db.commit()
            await emit(db, project.id, "task.completed", task.owner_agent, {"task_id": task.id, "label": task.payload.get("label")})

    # Process the first asset with outstanding work (one step per tick).
    assets = db.scalars(
        select(Asset).where(Asset.project_id == project.id).order_by(Asset.kind, Asset.name)
    ).all()
    for asset in assets:
        if asset.state in {AssetState.APPROVED, AssetState.ARCHIVED}:
            continue
        did_work = await _process_asset(db, project, asset)
        if did_work:
            return True
    return False


def project_counts(db: Session, project_id: str) -> dict[str, int]:
    return {
        "scenes": len(db.scalars(select(Scene).where(Scene.project_id == project_id)).all()),
        "environments": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.ENVIRONMENT)).all()),
        "characters": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.CHARACTER)).all()),
        "props": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.PROP)).all()),
        "tasks": len(db.scalars(select(Task).where(Task.project_id == project_id)).all()),
        "notifications": len(db.scalars(select(Event).where(Event.project_id == project_id, Event.read.is_(False))).all()),
    }


# --- Always-on background worker ----------------------------------------------

_workers: dict[str, asyncio.Task] = {}


async def _worker_loop(project_id: str) -> None:
    """Keep producing while the project is RUNNING."""
    while True:
        db = SessionLocal()
        try:
            project = db.get(Project, project_id)
            if not project or project.status != ProjectStatus.RUNNING:
                break
            did_work = await run_seed_tick(db, project)
        except Exception as exc:  # noqa: BLE001
            try:
                await emit(db, project_id, "worker.error", "producer", {"error": str(exc)})
            except Exception:  # noqa: BLE001
                pass
            did_work = False
        finally:
            db.close()
        # Idle a little longer when there's nothing to do.
        await asyncio.sleep(max(settings.tick_ms, 250) / 1000 if did_work else 3.0)

    _workers.pop(project_id, None)


def is_running(project_id: str) -> bool:
    task = _workers.get(project_id)
    return bool(task and not task.done())


async def start_project(db: Session, project: Project) -> Project:
    project.status = ProjectStatus.RUNNING
    db.commit()
    await ensure_seed_project(db, project)
    _ensure_tasks(db, project)
    await emit(db, project.id, "project.started", "producer", {"status": "RUNNING"})
    if not is_running(project.id):
        _workers[project.id] = asyncio.create_task(_worker_loop(project.id))
    return project


def stop_worker(project_id: str) -> None:
    task = _workers.get(project_id)
    if task and not task.done():
        task.cancel()
    _workers.pop(project_id, None)
