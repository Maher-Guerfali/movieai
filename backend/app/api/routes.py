from html import escape
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.assistant import run_assistant
from app.agents.mediator import apply_actions
from app.api.utils import to_asset_out, to_project_out
from app.db.session import get_db
from app.events.bus import emit, hub
from app.models.entities import Asset, AssetKind, AssetState, ChatMessage, Event, Image, Project, ProjectStatus, Scene, Task, UsageRecord
from app.orchestrator.service import ensure_seed_project, is_running, project_counts, start_project, stop_worker
from app.schemas.api import AssetOut, AssetPatch, ChatMessageOut, ChatRequest, ChatResponse, CommandRequest, EventOut, ProjectCreate, ProjectOut, RejectRequest, SceneOut, SeedRequest, TaskOut
from app.services.media import image_path
from app.services.usage import usage_summary

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
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.instruction = payload.instruction
    db.commit()
    try:
        await ensure_seed_project(db, project)
    except Exception as exc:  # noqa: BLE001 - surface a clear, actionable error
        await emit(db, project.id, "writer.error", "writer", {"error": str(exc)})
        raise HTTPException(502, f"Story generation failed: {exc}") from exc
    db.refresh(project)
    return to_project_out(db, project)


@router.post("/projects/{project_id}/start", response_model=ProjectOut)
async def start(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    try:
        await start_project(db, project)
    except Exception as exc:  # noqa: BLE001
        project.status = ProjectStatus.PAUSED
        db.commit()
        await emit(db, project.id, "writer.error", "producer", {"error": str(exc)})
        raise HTTPException(502, f"Could not start production: {exc}") from exc
    db.refresh(project)
    return to_project_out(db, project)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    stop_worker(project_id)
    # Tables without an ORM cascade relationship must be cleared explicitly.
    for row in db.scalars(select(ChatMessage).where(ChatMessage.project_id == project_id)).all():
        db.delete(row)
    for row in db.scalars(select(UsageRecord).where(UsageRecord.project_id == project_id)).all():
        db.delete(row)
    db.delete(project)
    db.commit()
    return {"deleted": True}


@router.post("/projects/{project_id}/pause", response_model=ProjectOut)
async def pause(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.status = ProjectStatus.PAUSED
    db.commit()
    stop_worker(project.id)
    await emit(db, project.id, "project.paused", "director", {})
    return to_project_out(db, project)


@router.post("/projects/{project_id}/resume", response_model=ProjectOut)
async def resume(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await start_project(db, project)
    db.refresh(project)
    await emit(db, project.id, "project.resumed", "director", {})
    return to_project_out(db, project)


@router.get("/projects/{project_id}/usage")
def usage(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    summary = usage_summary(db, project_id)
    summary["worker_running"] = is_running(project_id)
    return summary


@router.get("/projects/{project_id}/state")
def project_state(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    tasks = db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.priority)).all()
    events = db.scalars(select(Event).where(Event.project_id == project_id).order_by(Event.created_at.desc()).limit(12)).all()
    usage = usage_summary(db, project_id)
    usage["worker_running"] = is_running(project_id)
    return {
        "project": to_project_out(db, project),
        "counts": project_counts(db, project_id),
        "usage": usage,
        "tasks": [TaskOut.model_validate(task) for task in tasks],
        "events": [EventOut.model_validate(event) for event in events],
        "activity": {
            "producer": "Maintaining the seed production roadmap",
            "writer": "Screenplay and scene tree complete",
            "art_director": "Seed prompts and visual references prepared",
            "critic": "Reviewing references against the style bible",
            "asset_manager": "Filing approved assets and prompt history",
        },
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


@router.get("/assets/{asset_id}/images")
def asset_images(asset_id: str, db: Session = Depends(get_db)) -> list:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id).options(selectinload(Asset.images)))
    if not asset:
        raise HTTPException(404, "Asset not found")
    return to_asset_out(asset).images


@router.get("/assets/{asset_id}/prompts")
def asset_prompts(asset_id: str, db: Session = Depends(get_db)) -> list:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id).options(selectinload(Asset.prompts)))
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset.prompts


@router.get("/assets/{asset_id}/reviews")
def asset_reviews(asset_id: str, db: Session = Depends(get_db)) -> list:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id).options(selectinload(Asset.reviews)))
    if not asset:
        raise HTTPException(404, "Asset not found")
    return asset.reviews


@router.post("/projects/{project_id}/command")
async def command(project_id: str, payload: CommandRequest, db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    lowered = payload.text.lower()
    if "pause" in lowered or "stop" in lowered:
        project.status = ProjectStatus.PAUSED
        db.commit()
        stop_worker(project.id)
    elif "resume" in lowered or "continue" in lowered or "start" in lowered:
        await start_project(db, project)
    db.commit()
    await emit(db, project_id, "director.command_applied", "director", {"command": payload.text})
    return {"applied": True, "status": project.status.value}


def _chat_history(db: Session, project_id: str, limit: int = 50) -> list[ChatMessage]:
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.created_at)
    ).all()
    return rows[-limit:]


@router.get("/projects/{project_id}/chat", response_model=list[ChatMessageOut])
def get_chat(project_id: str, db: Session = Depends(get_db)) -> list[ChatMessageOut]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return [ChatMessageOut.model_validate(row) for row in _chat_history(db, project_id)]


@router.post("/projects/{project_id}/chat", response_model=ChatResponse)
async def post_chat(project_id: str, payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    history = [{"role": row.role, "content": row.content} for row in _chat_history(db, project_id, limit=20)]

    db.add(ChatMessage(project_id=project_id, role="user", agent="user", content=payload.text, actions=[]))
    db.commit()

    result = await run_assistant(db, project, payload.text, history)
    applied = await apply_actions(db, project, result["actions"])

    assistant_msg = ChatMessage(
        project_id=project_id,
        role="assistant",
        agent="assistant",
        content=result["reply"],
        actions=applied,
    )
    db.add(assistant_msg)
    db.commit()

    await emit(db, project_id, "assistant.replied", "assistant", {"actions": applied})

    return ChatResponse(
        reply=result["reply"],
        actions=applied,
        messages=[ChatMessageOut.model_validate(row) for row in _chat_history(db, project_id)],
    )


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
async def regenerate_asset(asset_id: str, db: Session = Depends(get_db)) -> AssetOut:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, "Asset not found")
    # Clear prior image + review so the worker produces a fresh pass. The prompt
    # is kept (and bumped) unless none exists yet.
    for review in list(asset.reviews):
        db.delete(review)
    for image in list(asset.images):
        db.delete(image)
    asset.state = AssetState.GENERATING
    db.commit()
    await emit(db, asset.project_id, "generation.queued", "director", {"asset_id": asset.id, "forced": True})
    return asset_detail(asset_id, db)


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
def tasks(project_id: str, db: Session = Depends(get_db)) -> list[TaskOut]:
    rows = db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.priority)).all()
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

    # Serve the real generated file when present.
    if row.minio_key:
        path = image_path(row.minio_key)
        if path:
            return FileResponse(str(path))

    # Fallback: stylized SVG placeholder (mock mode / generation pending).
    asset = db.get(Asset, row.asset_id)
    title = escape(asset.name if asset else "AI Movie Studio")
    palette = "#d7c39b" if row.state == AssetState.APPROVED else "#9aa685"
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{row.width}" height="{row.height}" viewBox="0 0 {row.width} {row.height}">
      <defs>
        <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="#171613"/>
          <stop offset="0.5" stop-color="#473f31"/>
          <stop offset="1" stop-color="#8b7650"/>
        </linearGradient>
        <pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse">
          <path d="M0 10 L10 0" stroke="#0d0d0b" stroke-width="1" opacity=".25"/>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
      <rect width="100%" height="100%" fill="url(#hatch)" opacity=".7"/>
      <circle cx="800" cy="140" r="190" fill="{palette}" opacity=".22"/>
      <path d="M0 438 C210 390 360 448 540 408 C745 362 824 410 1024 354 L1024 576 L0 576 Z" fill="#11110f" opacity=".74"/>
      <text x="54" y="82" fill="#efe7d2" font-family="Arial, sans-serif" font-size="38" font-weight="700">{title}</text>
      <text x="56" y="128" fill="#d7c39b" font-family="Arial, sans-serif" font-size="22">mock ComfyUI reference · seed {row.seed}</text>
      <text x="56" y="508" fill="#efe7d2" font-family="Arial, sans-serif" font-size="20">Waltz with Bashir style bible · ink · sepia · olive · restraint</text>
    </svg>
    """
    return Response(svg, media_type="image/svg+xml")


@router.websocket("/ws/projects/{project_id}")
async def websocket(project_id: str, websocket: WebSocket) -> None:
    await hub.connect(project_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(project_id, websocket)
