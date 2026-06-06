from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.models.entities import Event


NOTIFICATION_TYPES = {
    "phase.proposed",
    "phase.completed",
    "phase.failed",
    "image.created",
    "review.completed",
    "needs_director",
    "project.completed",
    "budget.exhausted",
}


class EventHub:
    def __init__(self) -> None:
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients[project_id].add(websocket)

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        self._clients[project_id].discard(websocket)

    async def publish(self, project_id: str, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in self._clients.get(project_id, set()):
            try:
                await websocket.send_json(event)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(project_id, websocket)


hub = EventHub()


async def emit(
    db: Session,
    project_id: str,
    event_type: str,
    actor: str,
    payload: dict[str, Any] | None = None,
) -> Event:
    event = Event(
        project_id=project_id,
        type=event_type,
        actor=actor,
        payload=payload or {},
        read=event_type not in NOTIFICATION_TYPES,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    await hub.publish(
        project_id,
        {
            "id": event.id,
            "project_id": project_id,
            "type": event.type,
            "actor": event.actor,
            "payload": event.payload,
            "read": event.read,
            "created_at": event.created_at.isoformat(),
        },
    )
    return event
