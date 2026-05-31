"""Mediator agent.

Turns the structured `actions` produced by the conversational assistant into
concrete edits against the production tree (the always-running writer / art
director / critic agents act on this shared state). This is the bridge between
the user's natural-language requests and the autonomous agents.
"""

from typing import Any

from sqlalchemy import select

from app.events.bus import emit
from app.models.entities import Asset, AssetState, Project, ProjectStatus
from app.orchestrator.service import start_project, stop_worker


def _find_asset(db, project_id: str, ref: str | None) -> Asset | None:
    if not ref:
        return None
    asset = db.get(Asset, ref)
    if asset and asset.project_id == project_id:
        return asset
    needle = ref.strip().lower()
    assets = db.scalars(select(Asset).where(Asset.project_id == project_id)).all()
    for asset in assets:
        if asset.name.lower() == needle:
            return asset
    for asset in assets:
        if needle in asset.name.lower():
            return asset
    return None


async def apply_actions(
    db, project: Project, actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Apply a list of assistant-proposed actions, returning a report per action."""
    applied: list[dict[str, Any]] = []

    for action in actions or []:
        action_type = (action.get("type") or "").lower()
        target = action.get("asset") or action.get("asset_id") or action.get("name")
        result: dict[str, Any] = {"type": action_type, "ok": True}

        if action_type in {"pause", "stop"}:
            project.status = ProjectStatus.PAUSED
            db.commit()
            stop_worker(project.id)
            await emit(db, project.id, "project.paused", "mediator", {"via": "chat"})
            result["detail"] = "Production paused."

        elif action_type in {"resume", "start", "continue"}:
            await start_project(db, project)
            await emit(db, project.id, "project.resumed", "mediator", {"via": "chat"})
            result["detail"] = "Production running."

        elif action_type in {"set_style", "style"}:
            new_style = action.get("style") or action.get("value")
            if new_style:
                project.style = new_style
                await emit(db, project.id, "project.style_changed", "mediator", {"style": new_style})
                result["detail"] = f"Style set to: {new_style}"
            else:
                result.update(ok=False, detail="No style provided.")

        elif action_type in {"update_asset", "edit_asset"}:
            asset = _find_asset(db, project.id, target)
            if not asset:
                result.update(ok=False, detail=f"Asset not found: {target}")
            else:
                if action.get("brief"):
                    asset.brief = action["brief"]
                if action.get("description"):
                    asset.description = action["description"]
                await emit(db, project.id, "asset.updated", "mediator", {"asset_id": asset.id})
                result["detail"] = f"Updated {asset.name}."
                result["asset_id"] = asset.id

        elif action_type in {"regenerate_asset", "regenerate"}:
            asset = _find_asset(db, project.id, target)
            if not asset:
                result.update(ok=False, detail=f"Asset not found: {target}")
            else:
                for review in list(asset.reviews):
                    db.delete(review)
                for image in list(asset.images):
                    db.delete(image)
                asset.state = AssetState.GENERATING
                await emit(
                    db, project.id, "generation.queued", "mediator",
                    {"asset_id": asset.id, "forced": True},
                )
                result["detail"] = f"Queued regeneration for {asset.name}."
                result["asset_id"] = asset.id

        elif action_type in {"approve_asset", "approve"}:
            asset = _find_asset(db, project.id, target)
            if not asset:
                result.update(ok=False, detail=f"Asset not found: {target}")
            else:
                asset.state = AssetState.APPROVED
                for image in asset.images:
                    image.state = AssetState.APPROVED
                await emit(
                    db, project.id, "asset.state_changed", "mediator",
                    {"asset_id": asset.id, "to": "APPROVED"},
                )
                result["detail"] = f"Approved {asset.name}."
                result["asset_id"] = asset.id

        elif action_type in {"reject_asset", "reject"}:
            asset = _find_asset(db, project.id, target)
            if not asset:
                result.update(ok=False, detail=f"Asset not found: {target}")
            else:
                asset.state = AssetState.REJECTED
                await emit(
                    db, project.id, "needs_director", "mediator",
                    {"asset_id": asset.id, "reason": action.get("notes", "Requested via chat.")},
                )
                result["detail"] = f"Rejected {asset.name} for another pass."
                result["asset_id"] = asset.id

        elif action_type in {"none", "note", ""}:
            result["detail"] = "No production change requested."

        else:
            result.update(ok=False, detail=f"Unknown action: {action_type}")

        applied.append(result)

    db.commit()
    return applied
