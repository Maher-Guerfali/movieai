"""Conversational assistant agent.

This is the always-available chat agent shown in the top-left of the dashboard.
It answers questions about the website / production and, when the user asks for
a change, returns structured `actions` that the mediator agent applies to the
production tree.
"""

import json
from typing import Any

from sqlalchemy import select

from app.models.entities import Asset, Event, Project, Scene
from app.providers.factory import get_provider

SYSTEM_PROMPT = """You are the on-site AI producer assistant for "AI Movie Studio",
a platform that autonomously turns a story/comic package into a ~1 hour animated film
(currently the production "Lili Marleen - Damascus" in a Waltz with Bashir style).

The studio runs several always-on agents on a shared production tree:
- writer: breaks the story into a screenplay, scenes and asset briefs.
- art_director: writes generation prompts and requests images.
- critic: reviews generated images against the brief and style bible.
- asset_manager: files approved assets.

Your job:
1. Answer the user's questions about the website, the production, its progress,
   scenes, characters, environments, props, tasks and agent activity. Use the
   PRODUCTION CONTEXT provided. Be concise and concrete.
2. When the user asks you to CHANGE something, also emit actions for the mediator
   agent to apply. Only emit actions the user clearly requested.

Respond ONLY with a JSON object of the form:
{
  "reply": "<your natural-language answer to the user>",
  "actions": [ { "type": "...", ... } ]
}

Supported action types (omit or use [] when nothing should change):
- {"type": "pause"} / {"type": "resume"}
- {"type": "set_style", "style": "<new style text>"}
- {"type": "update_asset", "asset": "<asset name>", "brief": "<new brief>", "description": "<optional>"}
- {"type": "regenerate_asset", "asset": "<asset name>"}
- {"type": "approve_asset", "asset": "<asset name>"}
- {"type": "reject_asset", "asset": "<asset name>", "notes": "<why>"}

Never invent assets that are not in the context. If a request is ambiguous, ask
for clarification in "reply" and return an empty "actions" list."""


def build_context(db, project: Project) -> str:
    scenes = db.scalars(
        select(Scene).where(Scene.project_id == project.id).order_by(Scene.scene_no)
    ).all()
    assets = db.scalars(
        select(Asset).where(Asset.project_id == project.id).order_by(Asset.name)
    ).all()
    events = db.scalars(
        select(Event)
        .where(Event.project_id == project.id)
        .order_by(Event.created_at.desc())
        .limit(8)
    ).all()

    lines = [
        f"Project: {project.name}",
        f"Style: {project.style}",
        f"Status: {project.status.value}",
        f"Scenes ({len(scenes)}): " + ", ".join(s.title for s in scenes) if scenes else "Scenes: none yet",
        "Assets:",
    ]
    for asset in assets:
        lines.append(f"  - [{asset.kind.value}] {asset.name} ({asset.state.value})")
    if not assets:
        lines.append("  (none yet)")
    lines.append("Recent activity:")
    for event in events:
        lines.append(f"  - {event.actor}: {event.type}")
    if not events:
        lines.append("  (none yet)")
    return "\n".join(lines)


async def run_assistant(
    db, project: Project, user_text: str, history: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Run the assistant for one user turn. Returns {"reply", "actions"}."""
    provider = get_provider()
    context = build_context(db, project)

    messages: list[dict[str, Any]] = []
    for turn in history or []:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append(
        {
            "role": "user",
            "content": f"PRODUCTION CONTEXT:\n{context}\n\nUSER MESSAGE:\n{user_text}",
        }
    )

    try:
        result = await provider.complete(SYSTEM_PROMPT, messages, json_schema={"type": "object"})
    except Exception as exc:  # noqa: BLE001 - surface a usable message to the UI
        return {
            "reply": (
                "I couldn't reach the language model. Check that USE_MOCK_AI is false "
                f"and your provider API key is valid. ({type(exc).__name__})"
            ),
            "actions": [],
        }

    parsed = result.get("json") or {}
    if not parsed and result.get("content"):
        try:
            parsed = json.loads(result["content"])
        except json.JSONDecodeError:
            parsed = {"reply": result["content"], "actions": []}

    reply = parsed.get("reply") or "Okay."
    actions = parsed.get("actions") or []
    if not isinstance(actions, list):
        actions = []
    return {"reply": reply, "actions": actions}
