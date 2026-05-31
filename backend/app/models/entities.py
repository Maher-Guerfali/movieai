import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProjectStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class AssetKind(str, enum.Enum):
    CHARACTER = "CHARACTER"
    ENVIRONMENT = "ENVIRONMENT"
    PROP = "PROP"


class AssetState(str, enum.Enum):
    TODO = "TODO"
    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_DIRECTOR = "NEEDS_DIRECTOR"
    ARCHIVED = "ARCHIVED"


class TaskStatus(str, enum.Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    GENERATING = "GENERATING"
    UNDER_REVIEW = "UNDER_REVIEW"
    DONE = "DONE"
    FAILED = "FAILED"
    NEEDS_DIRECTOR = "NEEDS_DIRECTOR"


def new_uuid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    style: Mapped[str] = mapped_column(Text)
    instruction: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)
    roadmap: Mapped[dict] = mapped_column(JSON, default=dict)

    scenes: Mapped[list["Scene"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list["Asset"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    act_no: Mapped[int] = mapped_column(Integer)
    scene_no: Mapped[int] = mapped_column(Integer)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(200))
    time_of_day: Mapped[str] = mapped_column(String(80), default="")
    shots: Mapped[list[dict]] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="scenes")


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[AssetKind] = mapped_column(Enum(AssetKind), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    brief: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[AssetState] = mapped_column(Enum(AssetState), default=AssetState.TODO)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="assets")
    prompts: Mapped[list["Prompt"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    images: Mapped[list["Image"]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(back_populates="asset", cascade="all, delete-orphan")


class Prompt(Base, TimestampMixin):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    agent: Mapped[str] = mapped_column(String(80))
    positive: Mapped[str] = mapped_column(Text)
    negative: Mapped[str] = mapped_column(Text)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)

    asset: Mapped[Asset] = relationship(back_populates="prompts")
    images: Mapped[list["Image"]] = relationship(back_populates="prompt", cascade="all, delete-orphan")


class Image(Base, TimestampMixin):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), index=True)
    minio_key: Mapped[str] = mapped_column(String(300))
    width: Mapped[int] = mapped_column(Integer, default=1024)
    height: Mapped[int] = mapped_column(Integer, default=576)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[AssetState] = mapped_column(Enum(AssetState), default=AssetState.UNDER_REVIEW)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    asset: Mapped[Asset] = relationship(back_populates="images")
    prompt: Mapped[Prompt] = relationship(back_populates="images")


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    image_id: Mapped[str | None] = mapped_column(ForeignKey("images.id"), nullable=True)
    critic_agent: Mapped[str] = mapped_column(String(80), default="critic")
    verdict: Mapped[str] = mapped_column(String(20))
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    prompt_suggestions: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="reviews")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[str] = mapped_column(String(120), index=True)
    owner_agent: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.TODO)
    priority: Mapped[int] = mapped_column(Integer, default=50)
    deps: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    retries: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="tasks")


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    type: Mapped[str] = mapped_column(String(120), index=True)
    actor: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    read: Mapped[bool] = mapped_column(default=False)

    project: Mapped[Project] = relationship(back_populates="events")


class ChatMessage(Base, TimestampMixin):
    """A single turn in the conversational-assistant thread for a project."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | assistant
    agent: Mapped[str] = mapped_column(String(80), default="assistant")
    content: Mapped[str] = mapped_column(Text)
    actions: Mapped[list] = mapped_column(JSON, default=list)
