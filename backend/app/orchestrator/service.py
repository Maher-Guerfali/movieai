"""Phase-gated production orchestrator.

The production advances one *phase* at a time. Each phase is first PROPOSED with
an itemized plan and waits for Director approval. On approval it RUNs (doing real
provider work), automatically REVIEWs its output, then proposes the next phase.
There is no one-shot run and no mock data — every item is produced by a real
agent/provider call.
"""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import art_director, critic, writer
from app.comfy.client import comfy
from app.core.config import settings
from app.events.bus import emit
from app.models.entities import (
    Asset,
    AssetKind,
    AssetState,
    Event,
    Image,
    Phase,
    PhaseStatus,
    Project,
    ProjectStatus,
    Prompt,
    Review,
    Scene,
    Task,
    TaskStatus,
)
from app.providers.base import ProviderError

GENERATED_DIR = Path(__file__).resolve().parents[2] / "generated"


# --------------------------------------------------------------------------- #
# Task helper
# --------------------------------------------------------------------------- #
async def _run_task(
    db: Session,
    project: Project,
    phase: Phase,
    task_type: str,
    owner: str,
    label: str,
    work: Callable[[], Awaitable[Any]],
) -> Any:
    task = Task(
        project_id=project.id,
        phase_id=phase.id,
        type=task_type,
        owner_agent=owner,
        status=TaskStatus.IN_PROGRESS,
        payload={"label": label},
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    await emit(db, project.id, "task.started", owner, {"task_id": task.id, "label": label, "phase_id": phase.id})
    try:
        result = await work()
    except Exception as exc:  # noqa: BLE001 — surfaced to the Director as a failed task
        task.status = TaskStatus.FAILED
        db.commit()
        await emit(db, project.id, "task.failed", owner, {"task_id": task.id, "label": label, "error": str(exc)})
        raise
    task.status = TaskStatus.DONE
    db.commit()
    await emit(db, project.id, "task.completed", owner, {"task_id": task.id, "label": label, "phase_id": phase.id})
    return result


def _project_assets(db: Session, project: Project) -> list[Asset]:
    return list(db.scalars(select(Asset).where(Asset.project_id == project.id).order_by(Asset.kind, Asset.name)).all())


# --------------------------------------------------------------------------- #
# Phase planners (compute the itemized plan shown for approval)
# --------------------------------------------------------------------------- #
def _plan_breakdown(db: Session, project: Project) -> list[dict]:
    return [
        {"key": "analyze", "kind": "story", "label": "Analyze source story & draft screenplay"},
        {"key": "scenes", "kind": "story", "label": "Break the story into scenes & shots"},
        {"key": "assets", "kind": "assets", "label": "Identify environments, characters & props"},
    ]


def _plan_per_asset(db: Session, project: Project, verb: str) -> list[dict]:
    return [
        {"key": asset.id, "kind": asset.kind.value, "target_id": asset.id, "label": f"{verb}: {asset.name}"}
        for asset in _project_assets(db, project)
    ]


def _plan_briefs(db: Session, project: Project) -> list[dict]:
    return _plan_per_asset(db, project, "Creative brief")


def _plan_prompts(db: Session, project: Project) -> list[dict]:
    return _plan_per_asset(db, project, "Image prompt")


def _plan_references(db: Session, project: Project) -> list[dict]:
    return _plan_per_asset(db, project, "Render & critic review")


# --------------------------------------------------------------------------- #
# Phase executors (do the real work, item by item)
# --------------------------------------------------------------------------- #
async def _exec_breakdown(db: Session, project: Project, phase: Phase) -> dict:
    data = await _run_task(
        db, project, phase, "story.analyze", "writer",
        "Analyze source story & draft screenplay",
        lambda: writer.analyze_story(project),
    )
    project.roadmap = {
        "screenplay": data.get("screenplay", ""),
        "milestone": "Breakdown complete; briefs next.",
    }
    db.commit()

    async def _build_scenes() -> int:
        for scene in data.get("scenes", []):
            db.add(
                Scene(
                    project_id=project.id,
                    act_no=int(scene.get("act_no", 1)),
                    scene_no=int(scene.get("scene_no", 1)),
                    slug=scene.get("slug", "scene"),
                    title=scene.get("title", "Scene"),
                    summary=scene.get("summary", ""),
                    location=scene.get("location", ""),
                    time_of_day=scene.get("time_of_day", ""),
                    shots=scene.get("shots", []),
                )
            )
        db.commit()
        return len(data.get("scenes", []))

    async def _build_assets() -> int:
        for item in data.get("assets", []):
            try:
                kind = AssetKind(str(item.get("kind", "PROP")).upper())
            except ValueError:
                kind = AssetKind.PROP
            db.add(
                Asset(
                    project_id=project.id,
                    kind=kind,
                    name=item.get("name", "Asset"),
                    description=item.get("description", ""),
                    state=AssetState.PLANNING,
                    metadata_json={"source": "writer.analyze_story"},
                )
            )
        db.commit()
        return len(data.get("assets", []))

    scenes = await _run_task(db, project, phase, "scenes.build", "writer", "Break the story into scenes & shots", _build_scenes)
    assets = await _run_task(db, project, phase, "assets.build", "writer", "Identify environments, characters & props", _build_assets)
    return {"scenes": scenes, "assets": assets}


async def _exec_briefs(db: Session, project: Project, phase: Phase) -> dict:
    count = 0
    for asset in _project_assets(db, project):
        async def _work(asset: Asset = asset) -> None:
            asset.brief = await writer.write_brief(project, asset)
            db.commit()
            await emit(db, project.id, "asset.updated", "writer", {"asset_id": asset.id})
        await _run_task(db, project, phase, "asset.brief", "writer", f"Creative brief: {asset.name}", _work)
        count += 1
    return {"briefs": count}


async def _exec_prompts(db: Session, project: Project, phase: Phase) -> dict:
    count = 0
    for asset in _project_assets(db, project):
        async def _work(asset: Asset = asset) -> None:
            prompt_data = await art_director.make_prompt(project, asset)
            prompt = Prompt(asset_id=asset.id, agent="art_director", **prompt_data)
            db.add(prompt)
            asset.state = AssetState.GENERATING
            db.commit()
            db.refresh(prompt)
            await emit(db, project.id, "prompt.created", "art_director", {"asset_id": asset.id, "prompt_id": prompt.id})
        await _run_task(db, project, phase, "asset.prompt", "art_director", f"Image prompt: {asset.name}", _work)
        count += 1
    return {"prompts": count}


async def _exec_references(db: Session, project: Project, phase: Phase) -> dict:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    approved = 0
    rejected = 0
    for asset in _project_assets(db, project):
        prompt = asset.prompts[-1] if asset.prompts else None
        if prompt is None:
            continue

        async def _work(asset: Asset = asset, prompt: Prompt = prompt) -> str:
            nonlocal approved, rejected
            params = prompt.params or {}
            ref = await comfy.generate(
                {"positive": prompt.positive, "negative": prompt.negative, "seed": prompt.seed, "params": params}
            )
            raw = await comfy.fetch_image(ref["filename"], ref.get("subfolder", ""), ref.get("type", "output"))

            image = Image(
                asset_id=asset.id,
                prompt_id=prompt.id,
                minio_key=ref["filename"],
                width=int(params.get("width", 1024)),
                height=int(params.get("height", 576)),
                seed=prompt.seed,
                state=AssetState.UNDER_REVIEW,
                meta={"comfy": ref},
            )
            db.add(image)
            asset.state = AssetState.UNDER_REVIEW
            db.commit()
            db.refresh(image)
            (GENERATED_DIR / f"{image.id}.png").write_bytes(raw)
            await emit(db, project.id, "image.created", "art_director", {"asset_id": asset.id, "image_id": image.id, "url": f"/api/images/{image.id}"})

            # Automatic critic review of the produced image.
            await emit(db, project.id, "review.started", "critic", {"asset_id": asset.id, "image_id": image.id})
            review_data = await critic.review_asset(project, asset, base64.b64encode(raw).decode())
            verdict = review_data["verdict"]
            db.add(Review(asset_id=asset.id, image_id=image.id, critic_agent="critic", **review_data))
            asset.state = AssetState.APPROVED if verdict == "APPROVED" else AssetState.REJECTED
            image.state = asset.state
            db.commit()
            if verdict == "APPROVED":
                approved += 1
            else:
                rejected += 1
            await emit(db, project.id, "review.completed", "critic", {"asset_id": asset.id, "image_id": image.id, "verdict": verdict, "scores": review_data.get("scores", {})})
            return verdict

        await _run_task(db, project, phase, "asset.render", "art_director", f"Render & critic review: {asset.name}", _work)
    return {"approved": approved, "rejected": rejected}


# --------------------------------------------------------------------------- #
# Pipeline definition
# --------------------------------------------------------------------------- #
PHASES: list[dict[str, Any]] = [
    {
        "key": "breakdown",
        "title": "Story & Breakdown",
        "description": "Writer analyzes the source story into a screenplay, scene tree, and the list of assets to build.",
        "planner": _plan_breakdown,
        "executor": _exec_breakdown,
    },
    {
        "key": "briefs",
        "title": "Creative Briefs",
        "description": "Writer writes a creative brief for every environment, character, and prop.",
        "planner": _plan_briefs,
        "executor": _exec_briefs,
    },
    {
        "key": "prompts",
        "title": "Prompt Engineering",
        "description": "Art Director turns each brief into a production-ready image prompt.",
        "planner": _plan_prompts,
        "executor": _exec_prompts,
    },
    {
        "key": "references",
        "title": "Reference Images & Review",
        "description": "Art Director renders each reference via ComfyUI, then the Critic reviews it automatically.",
        "planner": _plan_references,
        "executor": _exec_references,
    },
]


def _phase_spec(key: str) -> dict[str, Any]:
    return next(spec for spec in PHASES if spec["key"] == key)


def _active_phase(db: Session, project: Project) -> Phase | None:
    return db.scalar(
        select(Phase)
        .where(Phase.project_id == project.id, Phase.status.in_([PhaseStatus.PROPOSED, PhaseStatus.RUNNING, PhaseStatus.REVIEWING, PhaseStatus.FAILED]))
        .order_by(Phase.phase_no)
    )


def _done_count(db: Session, project: Project) -> int:
    return len(db.scalars(select(Phase).where(Phase.project_id == project.id, Phase.status == PhaseStatus.DONE)).all())


# --------------------------------------------------------------------------- #
# Public orchestration API
# --------------------------------------------------------------------------- #
async def propose_next_phase(db: Session, project: Project) -> Phase | None:
    """Create (or reset) the next phase as PROPOSED and await approval."""
    index = _done_count(db, project)
    if index >= len(PHASES):
        project.status = ProjectStatus.COMPLETED
        db.commit()
        await emit(db, project.id, "project.completed", "producer", {})
        return None

    spec = PHASES[index]
    phase_no = index + 1
    phase = db.scalar(select(Phase).where(Phase.project_id == project.id, Phase.phase_no == phase_no))
    if phase is None:
        phase = Phase(project_id=project.id, phase_no=phase_no, key=spec["key"], title=spec["title"], description=spec["description"])
        db.add(phase)
    phase.status = PhaseStatus.PROPOSED
    phase.plan = spec["planner"](db, project)
    phase.result = {}
    project.status = ProjectStatus.AWAITING_APPROVAL
    db.commit()
    db.refresh(phase)
    await emit(db, project.id, "phase.proposed", "producer", {"phase_id": phase.id, "phase_no": phase_no, "title": phase.title, "items": len(phase.plan)})
    return phase


async def start_project(db: Session, project: Project) -> Phase | None:
    """Begin the production: propose the first/next phase if none is active."""
    active = _active_phase(db, project)
    if active is not None:
        return active
    return await propose_next_phase(db, project)


async def approve_phase(db: Session, project: Project, phase: Phase) -> Phase:
    if phase.status not in (PhaseStatus.PROPOSED, PhaseStatus.FAILED):
        return phase
    phase.status = PhaseStatus.RUNNING
    project.status = ProjectStatus.RUNNING
    db.commit()
    await emit(db, project.id, "phase.approved", "director", {"phase_id": phase.id, "title": phase.title})

    spec = _phase_spec(phase.key)
    try:
        phase.status = PhaseStatus.REVIEWING if phase.key == "references" else PhaseStatus.RUNNING
        db.commit()
        result = await spec["executor"](db, project, phase)
    except ProviderError as exc:
        phase.status = PhaseStatus.FAILED
        phase.result = {"error": str(exc)}
        project.status = ProjectStatus.PAUSED
        db.commit()
        await emit(db, project.id, "phase.failed", "producer", {"phase_id": phase.id, "title": phase.title, "error": str(exc)})
        await emit(db, project.id, "needs_director", "producer", {"phase_id": phase.id, "reason": str(exc)})
        return phase

    phase.status = PhaseStatus.DONE
    phase.result = result
    db.commit()
    await emit(db, project.id, "phase.completed", "producer", {"phase_id": phase.id, "title": phase.title, "result": result})
    await propose_next_phase(db, project)
    return phase


async def regenerate_asset(db: Session, project: Project, asset: Asset) -> Asset:
    """Director-triggered single-asset re-run: new prompt → render → critic review."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    last_review = asset.reviews[-1] if asset.reviews else None
    version = (asset.prompts[-1].version + 1) if asset.prompts else 1

    prompt_data = await art_director.make_prompt(project, asset, version=version, critic=last_review)
    prompt = Prompt(asset_id=asset.id, agent="art_director", **prompt_data)
    db.add(prompt)
    asset.state = AssetState.GENERATING
    db.commit()
    db.refresh(prompt)
    await emit(db, project.id, "prompt.created", "art_director", {"asset_id": asset.id, "prompt_id": prompt.id})

    ref = await comfy.generate(
        {"positive": prompt.positive, "negative": prompt.negative, "seed": prompt.seed, "params": prompt.params or {}}
    )
    raw = await comfy.fetch_image(ref["filename"], ref.get("subfolder", ""), ref.get("type", "output"))
    image = Image(
        asset_id=asset.id,
        prompt_id=prompt.id,
        minio_key=ref["filename"],
        width=int((prompt.params or {}).get("width", 1024)),
        height=int((prompt.params or {}).get("height", 576)),
        seed=prompt.seed,
        state=AssetState.UNDER_REVIEW,
        meta={"comfy": ref},
    )
    db.add(image)
    asset.state = AssetState.UNDER_REVIEW
    db.commit()
    db.refresh(image)
    (GENERATED_DIR / f"{image.id}.png").write_bytes(raw)
    await emit(db, project.id, "image.created", "art_director", {"asset_id": asset.id, "image_id": image.id, "url": f"/api/images/{image.id}"})

    review_data = await critic.review_asset(project, asset, base64.b64encode(raw).decode())
    verdict = review_data["verdict"]
    db.add(Review(asset_id=asset.id, image_id=image.id, critic_agent="critic", **review_data))
    asset.state = AssetState.APPROVED if verdict == "APPROVED" else AssetState.REJECTED
    image.state = asset.state
    db.commit()
    await emit(db, project.id, "review.completed", "critic", {"asset_id": asset.id, "image_id": image.id, "verdict": verdict})
    return asset


async def reject_phase(db: Session, project: Project, phase: Phase, notes: str = "") -> Phase:
    phase.status = PhaseStatus.REJECTED
    project.status = ProjectStatus.PAUSED
    db.commit()
    await emit(db, project.id, "phase.rejected", "director", {"phase_id": phase.id, "title": phase.title, "notes": notes})
    return phase


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #
def project_counts(db: Session, project_id: str) -> dict[str, int]:
    return {
        "scenes": len(db.scalars(select(Scene).where(Scene.project_id == project_id)).all()),
        "environments": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.ENVIRONMENT)).all()),
        "characters": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.CHARACTER)).all()),
        "props": len(db.scalars(select(Asset).where(Asset.project_id == project_id, Asset.kind == AssetKind.PROP)).all()),
        "phases": len(db.scalars(select(Phase).where(Phase.project_id == project_id)).all()),
        "tasks": len(db.scalars(select(Task).where(Task.project_id == project_id)).all()),
        "notifications": len(db.scalars(select(Event).where(Event.project_id == project_id, Event.read.is_(False))).all()),
    }
