from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.entities import AssetKind, AssetState, PhaseStatus, ProjectStatus, TaskStatus


class ProjectCreate(BaseModel):
    name: str
    style: str = "Waltz with Bashir, inked war-memory animation"


class SeedRequest(BaseModel):
    instruction: str = "Make an AI movie out of this comic/story in Waltz with Bashir style."


class CommandRequest(BaseModel):
    text: str


class RejectRequest(BaseModel):
    notes: str


class AssetPatch(BaseModel):
    description: str | None = None
    brief: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    style: str
    instruction: str
    status: ProjectStatus
    roadmap: dict[str, Any]
    counts: dict[str, int] = {}
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SceneOut(BaseModel):
    id: str
    act_no: int
    scene_no: int
    slug: str
    title: str
    summary: str
    location: str
    time_of_day: str
    shots: list[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class PromptOut(BaseModel):
    id: str
    agent: str
    positive: str
    negative: str
    params: dict[str, Any]
    seed: int
    version: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageOut(BaseModel):
    id: str
    minio_key: str
    width: int
    height: int
    seed: int
    state: AssetState
    meta: dict[str, Any]
    url: str

    model_config = ConfigDict(from_attributes=True)


class ReviewOut(BaseModel):
    id: str
    image_id: str | None
    critic_agent: str
    verdict: str
    scores: dict[str, Any]
    issues: list[Any]
    prompt_suggestions: dict[str, Any]
    notes: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetOut(BaseModel):
    id: str
    project_id: str
    kind: AssetKind
    name: str
    description: str
    brief: str
    state: AssetState
    metadata_json: dict[str, Any]
    prompts: list[PromptOut] = []
    images: list[ImageOut] = []
    reviews: list[ReviewOut] = []

    model_config = ConfigDict(from_attributes=True)


class TaskOut(BaseModel):
    id: str
    phase_id: str | None = None
    type: str
    owner_agent: str
    status: TaskStatus
    priority: int
    deps: list[Any]
    payload: dict[str, Any]
    retries: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PhaseOut(BaseModel):
    id: str
    phase_no: int
    key: str
    title: str
    description: str
    status: PhaseStatus
    plan: list[dict[str, Any]]
    result: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventOut(BaseModel):
    id: str
    project_id: str
    type: str
    actor: str
    payload: dict[str, Any]
    read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
