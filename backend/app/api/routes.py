from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.utils import to_asset_out, to_project_out
from app.db.session import get_db
from app.events.bus import emit, hub
from app.models.entities import Asset, AssetKind, AssetState, Event, Image, Phase, PhaseStatus, Project, ProjectStatus, Scene, Task
from app.orchestrator.service import (
    GENERATED_DIR,
    approve_phase,
    project_counts,
    propose_next_phase,
    regenerate_asset,
    reject_phase,
    start_project,
)
from app.schemas.api import (
    AssetOut,
    AssetPatch,
    CommandRequest,
    EventOut,
    PhaseOut,
    ProjectCreate,
    ProjectOut,
    RejectRequest,
    SceneOut,
    SeedRequest,
    TaskOut,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"ok": True, "service": "movieai-backend"}


@router.post("/projects", response_model=ProjectOut)
async def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(name=payload.name, style=payload.style)
    db.add(project)
    db.commit()
    db.refresh(project)
    await emit(db, project.id, "project.created", "producer", {"name": project.name})
    return to_project_out(db, project)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return [to_project_out(db, project) for project in projects]


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return to_project_out(db, project)


@router.post("/projects/{project_id}/seed", response_model=ProjectOut)
async def seed_project(project_id: str, payload: SeedRequest, db: Session = Depends(get_db)) -> ProjectOut:
    """Record the Director's top instruction. Content is produced by phases, not seeded."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.instruction = payload.instruction
    db.commit()
    db.refresh(project)
    return to_project_out(db, project)


@router.post("/projects/{project_id}/start", response_model=ProjectOut)
async def start(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await start_project(db, project)
    db.refresh(project)
    return to_project_out(db, project)


@router.post("/projects/{project_id}/pause", response_model=ProjectOut)
async def pause(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.status = ProjectStatus.PAUSED
    db.commit()
    await emit(db, project.id, "project.paused", "director", {})
    return to_project_out(db, project)


@router.post("/projects/{project_id}/resume", response_model=ProjectOut)
async def resume(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await start_project(db, project)
    db.refresh(project)
    return to_project_out(db, project)


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #
@router.get("/projects/{project_id}/phases", response_model=list[PhaseOut])
def phases(project_id: str, db: Session = Depends(get_db)) -> list[PhaseOut]:
    rows = db.scalars(select(Phase).where(Phase.project_id == project_id).order_by(Phase.phase_no)).all()
    return [PhaseOut.model_validate(row) for row in rows]


@router.post("/phases/{phase_id}/approve", response_model=PhaseOut)
async def approve_phase_route(phase_id: str, db: Session = Depends(get_db)) -> PhaseOut:
    phase = db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, "Phase not found")
    project = db.get(Project, phase.project_id)
    await approve_phase(db, project, phase)
    db.refresh(phase)
    return PhaseOut.model_validate(phase)


@router.post("/phases/{phase_id}/reject", response_model=PhaseOut)
async def reject_phase_route(phase_id: str, payload: RejectRequest, db: Session = Depends(get_db)) -> PhaseOut:
    phase = db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, "Phase not found")
    project = db.get(Project, phase.project_id)
    await reject_phase(db, project, phase, payload.notes)
    db.refresh(phase)
    return PhaseOut.model_validate(phase)


@router.get("/projects/{project_id}/state")
def project_state(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    tasks = db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at)).all()
    events = db.scalars(select(Event).where(Event.project_id == project_id).order_by(Event.created_at.desc()).limit(15)).all()
    all_phases = db.scalars(select(Phase).where(Phase.project_id == project_id).order_by(Phase.phase_no)).all()
    current = next(
        (p for p in all_phases if p.status in (PhaseStatus.PROPOSED, PhaseStatus.RUNNING, PhaseStatus.REVIEWING, PhaseStatus.FAILED)),
        None,
    )
    return {
        "project": to_project_out(db, project),
        "counts": project_counts(db, project_id),
        "phases": [PhaseOut.model_validate(p) for p in all_phases],
        "current_phase": PhaseOut.model_validate(current) if current else None,
        "tasks": [TaskOut.model_validate(task) for task in tasks],
        "events": [EventOut.model_validate(event) for event in events],
    }


def list_assets(project_id: str, kind: AssetKind, db: Session) -> list[AssetOut]:
    assets = db.scalars(
        select(Asset)
        .where(Asset.project_id == project_id, Asset.kind == kind)
        .options(selectinload(Asset.prompts), selectinload(Asset.images), selectinload(Asset.reviews))
        .order_by(Asset.name)
    ).all()
    return [to_asset_out(asset) for asset in assets]


@router.get("/projects/{project_id}/environments", response_model=list[AssetOut])
def environments(project_id: str, db: Session = Depends(get_db)) -> list[AssetOut]:
    return list_assets(project_id, AssetKind.ENVIRONMENT, db)


@router.get("/projects/{project_id}/characters", response_model=list[AssetOut])
def characters(project_id: str, db: Session = Depends(get_db)) -> list[AssetOut]:
    return list_assets(project_id, AssetKind.CHARACTER, db)


@router.get("/projects/{project_id}/props", response_model=list[AssetOut])
def props(project_id: str, db: Session = Depends(get_db)) -> list[AssetOut]:
    return list_assets(project_id, AssetKind.PROP, db)


@router.get("/projects/{project_id}/scenes", response_model=list[SceneOut])
def scenes(project_id: str, db: Session = Depends(get_db)) -> list[SceneOut]:
    rows = db.scalars(select(Scene).where(Scene.project_id == project_id).order_by(Scene.scene_no)).all()
    return [SceneOut.model_validate(row) for row in rows]


@router.get("/projects/{project_id}/screenplay")
def screenplay(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {"screenplay": project.roadmap.get("screenplay", ""), "roadmap": project.roadmap}


@router.get("/assets/{asset_id}", response_model=AssetOut)
def asset_detail(asset_id: str, db: Session = Depends(get_db)) -> AssetOut:
    asset = db.scalar(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(selectinload(Asset.prompts), selectinload(Asset.images), selectinload(Asset.reviews))
    )
    if not asset:
        raise HTTPException(404, "Asset not found")
    return to_asset_out(asset)


@router.post("/projects/{project_id}/command")
async def command(project_id: str, payload: CommandRequest, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    lowered = payload.text.lower()
    if "pause" in lowered:
        project.status = ProjectStatus.PAUSED
        db.commit()
    elif "resume" in lowered or "continue" in lowered or "start" in lowered:
        await start_project(db, project)
    await emit(db, project_id, "director.command_applied", "director", {"command": payload.text})
    db.refresh(project)
    return {"applied": True, "status": project.status.value}


@router.patch("/assets/{asset_id}", response_model=AssetOut)
async def patch_asset(asset_id: str, payload: AssetPatch, db: Session = Depends(get_db)) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    if payload.description is not None:
        asset.description = payload.description
    if payload.brief is not None:
        asset.brief = payload.brief
    db.commit()
    await emit(db, asset.project_id, "asset.updated", "director", {"asset_id": asset.id})
    return asset_detail(asset_id, db)


@router.post("/assets/{asset_id}/approve", response_model=AssetOut)
async def approve_asset(asset_id: str, db: Session = Depends(get_db)) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.state = AssetState.APPROVED
    for image in asset.images:
        image.state = AssetState.APPROVED
    db.commit()
    await emit(db, asset.project_id, "asset.state_changed", "director", {"asset_id": asset.id, "to": "APPROVED"})
    return asset_detail(asset_id, db)


@router.post("/assets/{asset_id}/reject", response_model=AssetOut)
async def reject_asset(asset_id: str, payload: RejectRequest, db: Session = Depends(get_db)) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    asset.state = AssetState.REJECTED
    db.commit()
    await emit(db, asset.project_id, "needs_director", "director", {"asset_id": asset.id, "reason": payload.notes})
    return asset_detail(asset_id, db)


@router.post("/assets/{asset_id}/regenerate", response_model=AssetOut)
async def regenerate(asset_id: str, db: Session = Depends(get_db)) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    project = db.get(Project, asset.project_id)
    await regenerate_asset(db, project, asset)
    return asset_detail(asset_id, db)


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
def tasks(project_id: str, db: Session = Depends(get_db)) -> list[TaskOut]:
    rows = db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.created_at)).all()
    return [TaskOut.model_validate(row) for row in rows]


@router.get("/projects/{project_id}/notifications", response_model=list[EventOut])
def notifications(project_id: str, db: Session = Depends(get_db)) -> list[EventOut]:
    rows = db.scalars(select(Event).where(Event.project_id == project_id).order_by(Event.created_at.desc())).all()
    return [EventOut.model_validate(row) for row in rows if not row.read]


@router.post("/notifications/{event_id}/read")
def read_notification(event_id: str, db: Session = Depends(get_db)) -> dict:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "Notification not found")
    event.read = True
    db.commit()
    return {"read": True}


@router.get("/images/{image_id}")
def image(image_id: str, db: Session = Depends(get_db)) -> Response:
    row = db.get(Image, image_id)
    if not row:
        raise HTTPException(404, "Image not found")
    path = Path(GENERATED_DIR) / f"{image_id}.png"
    if not path.exists():
        raise HTTPException(404, "Image file not available")
    return Response(path.read_bytes(), media_type="image/png")


@router.websocket("/ws/projects/{project_id}")
async def websocket(project_id: str, websocket: WebSocket) -> None:
    await hub.connect(project_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(project_id, websocket)
