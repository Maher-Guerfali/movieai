# AI MOVIE STUDIO — BUILD SPECIFICATION

> **This is a build brief for an AI coding agent (Claude Code / Codex).**
> Read it top to bottom, then build the repository it describes.
> It is self-contained: everything you need to scaffold, architect, and
> ship the MVP is here. Where a detail is unspecified, choose the simplest
> option that satisfies the acceptance criteria and write it down.

---

## 0. How to use this document (instructions to the build agent)

You are building an **autonomous AI movie production studio**. A human
(the *Director*) feeds it a comic + story and a single instruction such as
*"make me an AI movie out of this comic."* From there, a team of AI agents
runs **continuously** — writing the screenplay, designing characters and
environments, generating images via ComfyUI, reviewing them, and moving
work forward — while the Director watches live progress, gets
notifications, sees images appear, and can **interrupt by voice or text at
any time** to steer the production.

Build in the **milestone order** in §15. Do not try to build everything at
once. Each milestone has acceptance criteria; a milestone is "done" only
when those pass. Commit after each milestone.

Rules:
- Keep the system **provider-agnostic** behind adapters (§5.1), but ship
  the default mapping the Director asked for: **GPT = visuals/images,
  Claude = story + technical, Gemini = review/critique.**
- Everything the agents do must produce **events** (§8) so the UI can show
  live progress and notifications.
- Every generated asset has an explicit **state** (§6.2) and an **owner
  agent**. Nothing is silently dropped.
- The autonomy loop must be **pausable and resumable** and survive a
  process restart (state lives in Postgres, not memory).
- **Never** hardcode API keys. Read from environment (§13).

---

## 1. Vision & the one-sentence goal

**Goal:** Turn a comic PDF + story text + character/style references into a
complete animated-movie production package — and keep producing
autonomously until the Director says stop.

**The Director's mental model (honor it):**
- *GPT* owns the **visual** side — it writes image prompts and drives image
  generation (the pixels come from ComfyUI; GPT is the Art Director that
  commands it).
- *Claude* owns the **story and technical** side — screenplay, scene
  breakdown, shot lists, continuity, and the technical/orchestration plan.
- *Gemini* is the **critic/helper** — it reviews generated images against
  the brief, approves or rejects, and assists the other two.
- The three run in a loop: Claude says *what* to make and writes the brief →
  GPT writes prompts and generates → Gemini + Claude inspect the result →
  approve and move to the next item, or reject and iterate the prompt.

**First production (the seed):** *"Lili Marleen – Damascus"* — see
`seed/story.md` and `seed/character_bible.md`. Visual style: **Waltz with
Bashir**, oscillating between rotoscoped-real and hand-drawn animation.

---

## 2. Scope

### Phase 1 — MVP (build this first, fully)
A running system that, given the seed story, autonomously:
1. Analyzes the story → produces a **screenplay** + **scene breakdown** +
   **shot list** (Claude).
2. Extracts and builds **Character**, **Environment**, and **Prop** bibles
   (Claude + GPT).
3. Generates **image prompts** per asset (GPT) and runs them through
   **ComfyUI** to produce reference images.
4. **Reviews** each image (Gemini) → APPROVED / REJECTED with notes; on
   reject, iterates the prompt and regenerates (bounded retries).
5. Streams **live progress + notifications** over WebSockets.
6. Lets the Director **interrupt by text or voice** to pause, redirect,
   approve, or edit — and the agents incorporate it and continue.
7. Dashboard with the left-nav drill-down: **Environments / Characters /
   Props / Story / Storyboards / Tasks / Notifications / Settings**, where
   clicking an Environment shows its places, and clicking a place shows its
   description, prompt history, generated images, and approval state.

### Phase 2+ — Later (stub the data model, don't build yet)
Automatic storyboard assembly, animation generation, voice synthesis, music,
editing timeline, trailer generation. Leave tables/enum values and
nav items present but mark them "coming soon."

---

## 3. Glossary

- **Director** — the human user. Has final say; interrupts anytime.
- **Agent** — an autonomous AI worker (Director/Producer, Writer, Art
  Director, Critic, Asset Manager). Backed by a provider (GPT/Claude/Gemini).
- **Project** — one movie production. Contains the whole tree (§6.1).
- **Asset** — anything produced and tracked: a Character, Environment, Prop,
  Image, Screenplay, Shot, Storyboard, Review. Has a state (§6.2).
- **Task** — a unit of work assigned to an agent (e.g. *"generate Afghan
  Camp environment references"*). Tasks form the autonomy queue.
- **Tick** — one iteration of the orchestration loop.
- **HITL** — human-in-the-loop interrupt (voice/text Director command).

---

## 4. System architecture

```
                         ┌─────────────────────────────────────────────┐
                         │                FRONTEND (Next.js)            │
                         │  Dashboard · Drill-down views · Live progress │
                         │  Notifications · Voice button · Image viewer  │
                         └───────────────▲───────────────▲──────────────┘
                                  REST / │   WebSocket    │ (events, progress,
                                         │                │  notifications, images)
                         ┌───────────────┴────────────────┴──────────────┐
                         │                 BACKEND (FastAPI)              │
                         │  REST API · WS hub · Auth · Voice ingest       │
                         │  Event bus (publish to WS + persist)           │
                         └───┬───────────────┬───────────────────┬───────┘
                             │               │                   │
              ┌──────────────▼──┐   ┌─────────▼─────────┐  ┌──────▼───────────┐
              │  ORCHESTRATOR    │   │   AGENT WORKERS    │  │  IMAGE PIPELINE  │
              │  (LangGraph)     │   │  Director/Producer │  │  ComfyUI client  │
              │  continuous loop │◀─▶│  Writer (Claude)   │  │  queue · poll ·  │
              │  tick · HITL     │   │  ArtDir (GPT)      │  │  retrieve · meta │
              │  pause/resume    │   │  Critic (Gemini)   │  └──────┬───────────┘
              └───────┬──────────┘   │  AssetMgr          │         │
                      │              └─────────┬──────────┘         │
                      │                        │                    │
        ┌─────────────▼──────┐   ┌─────────────▼──────┐   ┌─────────▼─────────┐
        │  PostgreSQL         │   │   Qdrant (vectors) │   │   MinIO (objects) │
        │  projects, assets,  │   │  prompt/asset      │   │   images, refs,   │
        │  tasks, reviews,    │   │  embeddings,       │   │   datasets        │
        │  events, prompts    │   │  continuity search │   │                   │
        └─────────────────────┘   └────────────────────┘   └───────────────────┘
```

Services (one container each): `frontend`, `backend`, `orchestrator`
(can be same process as backend in MVP, separate worker preferred),
`postgres`, `qdrant`, `minio`, and an **external** ComfyUI endpoint
(configurable URL — may be local GPU box, RunPod, etc.).

---

## 5. Agent system

### 5.1 Provider abstraction (build this first inside the backend)

Create an `LLMProvider` interface so any agent can run on any backend:

```python
class LLMProvider(Protocol):
    name: str  # "openai" | "anthropic" | "google"
    async def complete(self, system: str, messages: list[Msg],
                       tools: list[Tool] | None = None,
                       json_schema: dict | None = None) -> Completion: ...
    async def vision(self, system: str, images: list[ImageRef],
                     prompt: str) -> Completion: ...  # for the Critic
```

Implementations: `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider`.
Configure model IDs via env (§13) so they can be upgraded without code
changes. Default capability mapping:

| Agent              | Default provider | Primary capability used        |
|--------------------|------------------|--------------------------------|
| Director/Producer  | GPT (OpenAI)     | planning, tool-use, scheduling |
| Writer             | Claude (Anthropic)| long-form writing, structure  |
| Art Director       | GPT (OpenAI)     | prompt-craft, ComfyUI control  |
| Critic             | Gemini (Google)  | multimodal image review        |
| Asset Manager      | any (cheap model)| tagging, organizing            |

> The mapping is configuration, not hardcoding. The Director can reassign
> any agent to any provider in Settings.

### 5.2 Agent definitions

Each agent is a class with: `role`, `provider`, `system_prompt`,
`allowed_tools`, and a `handle(task) -> TaskResult` method. Full system
prompts live in `docs/AGENTS.md`; summaries here.

**Director / Producer (GPT)** — Owns the production plan. Decomposes the
top-level instruction into a prioritized **task graph**, assigns tasks to
agents, maintains project memory, decides what to do next each tick, and
folds in Director (human) interrupts. Output: tasks (created/updated),
roadmap updates, status summaries.

**Writer (Claude)** — Story analysis → screenplay → scene breakdown →
shot list → dialogue → continuity checks. Also writes the **creative brief**
for each visual asset (what a character/environment must convey) that the
Art Director turns into prompts. Output: screenplay docs, scenes, shots,
character/environment/prop briefs, continuity notes.

**Art Director (GPT)** — Maintains the **style bible**; turns briefs into
**image prompts** (positive/negative, params, seed strategy); plans LoRA
datasets; ensures character/environment consistency across shots. Drives the
image pipeline. Output: prompt records, generation tasks, style-bible updates.

**Critic (Gemini)** — Reviews each generated image **against** the brief +
style bible + prior approved refs (multimodal). Returns a structured verdict
(§5.4). Output: Review records (APPROVED/REJECTED + scored notes +
improvement suggestions).

**Asset Manager (any cheap model)** — Files images into MinIO, tags assets,
maintains versions, tracks approval status, links scenes↔assets, writes
embeddings to Qdrant for continuity search. Output: organized, tagged,
linked assets.

### 5.3 The autonomous orchestration loop (LangGraph)

The orchestrator runs **continuously** as long as the project is `RUNNING`.
State is persisted (Postgres) so it survives restarts. One **tick**:

```
loop while project.status == RUNNING:
    1. DRAIN_INTERRUPTS:
         pull any pending Director commands (voice/text) from the
         interrupt queue; let Director/Producer agent re-prioritize the
         task graph accordingly. Emit events for each applied command.
    2. PICK_TASK:
         select the highest-priority task in state TODO whose
         dependencies are satisfied. If none, idle-wait (sleep tick_ms)
         and continue (do NOT busy-spin).
    3. DISPATCH:
         set task -> IN_PROGRESS; route to its owner agent.
         emit task.started.
    4. EXECUTE:
         agent.handle(task). For generation tasks this enqueues ComfyUI
         work and the task parks in GENERATING until images return.
    5. REVIEW (for image-producing tasks):
         Critic reviews each produced image -> APPROVED | REJECTED.
         On REJECTED and retries_left > 0: Art Director iterates the
         prompt; create a follow-up GENERATING task; decrement retries.
         On REJECTED and retries_left == 0: mark NEEDS_DIRECTOR and notify.
    6. COMMIT:
         persist results; Asset Manager files/tags/links/embeds.
         set task -> DONE (or spawn child tasks the agent requested).
         emit task.completed + any asset.* events.
    7. PLAN_NEXT:
         Director/Producer inspects state; spawns the next tasks
         (e.g. after environments -> characters -> props -> shots).
    8. CHECKPOINT:
         save loop state + budget counters to Postgres.
```

Key properties:
- **Pause/Resume:** a Director command `pause` flips `project.status` to
  `PAUSED`; the loop finishes the current atomic step, checkpoints, and
  idles. `continue` resumes.
- **Idempotency:** each task carries a unique id; re-running a checkpoint
  must not double-generate. Use task state + a generation dedupe key
  (prompt hash + seed).
- **Concurrency:** allow N generation tasks in flight (config
  `MAX_CONCURRENT_GENERATIONS`), but keep planning deterministic.
- **Budget safety (§5.5):** before any paid call, check the budget guard.

### 5.4 Critic review rubric (structured output)

Critic returns JSON:

```json
{
  "asset_id": "uuid",
  "verdict": "APPROVED | REJECTED",
  "scores": {
    "brief_match": 0-10,
    "style_consistency": 0-10,
    "character_consistency": 0-10,
    "technical_quality": 0-10,
    "anatomy_artifacts": 0-10
  },
  "issues": ["short, specific problems"],
  "prompt_suggestions": {
    "add": ["..."], "remove": ["..."], "negative_add": ["..."]
  },
  "notes": "one paragraph"
}
```

Approval threshold is configurable (default: APPROVED requires
`brief_match>=7 AND style_consistency>=7 AND no critical anatomy issue`).
When the Critic rejects, its `prompt_suggestions` feed the Art Director's
next iteration.

### 5.5 Budget & rate safety

- Per-project **daily token budget** and **daily generation budget** (env
  defaults, editable in Settings).
- A `BudgetGuard` checked before every provider/ComfyUI call. On exhaustion:
  pause the project, emit `budget.exhausted` notification, wait for Director.
- Exponential backoff + jitter on provider/ComfyUI errors; max retries
  configurable. Persist failures as events.

---

## 6. Data model (PostgreSQL)

### 6.1 Project tree

```
Project
├── Acts            (act_no, title, summary)
├── Scenes          (act_id, scene_no, slug, summary, location, time_of_day)
├── Shots           (scene_id, shot_no, description, camera, duration_s)
├── Characters      (name, biography, relationships, costume_variants, emotions)
├── Environments    (name, description, references, related_scene_ids)   ← "places"
├── Props           (name, description, related_scene_ids)
├── Prompts         (asset_id, agent, positive, negative, params, seed, version)
├── Images          (prompt_id, minio_key, width, height, seed, meta, state)
├── Storyboards     (scene_id, ordered image_ids)            [Phase 2 stub]
├── Animations      (...)                                    [Phase 2 stub]
├── Audio           (...)                                    [Phase 2 stub]
├── Reviews         (asset_id, critic_agent, verdict, scores, issues, notes)
├── Tasks           (type, owner_agent, status, priority, deps, payload, retries)
└── Events          (type, actor, payload, ts)   ← drives the live UI + history
```

Implement with SQLAlchemy + Alembic migrations. Use UUID PKs, `created_at`/
`updated_at` on every table, soft-delete (`archived_at`) instead of hard
delete. Store flexible fields (`params`, `payload`, `meta`, `relationships`)
as JSONB.

### 6.2 Asset state machine

```
TODO ──▶ PLANNING ──▶ GENERATING ──▶ UNDER_REVIEW ──▶ APPROVED
  ▲                        │               │            │
  │                        │               └──▶ REJECTED ┘
  │                        │                     │
  └─────────── (retry) ◀───┴─────────────────────┘
                                                  ▼
                                         NEEDS_DIRECTOR ──▶ (human acts)
                                                  ▼
                                              ARCHIVED
```

Every asset and task carries one of:
`TODO · PLANNING · GENERATING · UNDER_REVIEW · APPROVED · REJECTED ·
NEEDS_DIRECTOR · ARCHIVED`. State transitions are the only way state
changes, and **every transition emits an event** (§8).

---

## 7. Backend API (FastAPI)

REST (JSON) + one WebSocket. All under `/api`. Auth: single-user MVP with a
bearer token from env (`API_TOKEN`); structure for multi-user later.

### Projects & production
```
POST   /api/projects                      create project (name, style)
GET    /api/projects/{id}                  project + summary counts
POST   /api/projects/{id}/seed             upload comic/story/refs, set the
                                           top instruction ("make a movie…")
POST   /api/projects/{id}/start            status -> RUNNING (autonomy on)
POST   /api/projects/{id}/pause            status -> PAUSED
POST   /api/projects/{id}/resume           status -> RUNNING
GET    /api/projects/{id}/state            live agent activity + queue
```

### Tree resources (list/detail; all read in MVP, write where noted)
```
GET    /api/projects/{id}/environments               list "places"
GET    /api/environments/{eid}                        description, refs,
                                                       prompt history, images,
                                                       reviews, state, scenes
GET    /api/projects/{id}/characters     GET /api/characters/{cid}
GET    /api/projects/{id}/props          GET /api/props/{pid}
GET    /api/projects/{id}/scenes         GET /api/scenes/{sid}
GET    /api/projects/{id}/screenplay
GET    /api/assets/{aid}/images          GET /api/images/{imgid}  (streams file)
GET    /api/assets/{aid}/prompts
GET    /api/assets/{aid}/reviews
```

### Director actions (human-in-the-loop)
```
POST   /api/projects/{id}/command         {text} OR {audio} -> parsed command,
                                          pushed to interrupt queue (§9)
POST   /api/assets/{aid}/approve          Director override -> APPROVED
POST   /api/assets/{aid}/reject           {notes} -> REJECTED + re-queue
PATCH  /api/assets/{aid}                  Director edits brief/desc/prompt
POST   /api/assets/{aid}/regenerate       force a new generation iteration
```

### Tasks & notifications
```
GET    /api/projects/{id}/tasks           queue + statuses
GET    /api/projects/{id}/notifications   notification history
POST   /api/notifications/{nid}/read
```

### Realtime
```
WS     /api/ws/projects/{id}              subscribe to all project events (§8)
```

Return shapes are typed (Pydantic). Document with the auto OpenAPI at
`/docs`.

---

## 8. Realtime events & notifications

Single event envelope, published to the WS hub **and** persisted to the
`events` table (so the UI can replay history and the notification center is
just a filtered view of events).

```json
{
  "id": "uuid",
  "project_id": "uuid",
  "type": "task.started",
  "actor": "art_director",
  "ts": "2026-05-29T12:00:00Z",
  "payload": { "task_id": "…", "label": "Generate Afghan Camp references" }
}
```

Event types (at minimum):
```
project.started / project.paused / project.resumed
agent.activity            // {agent, activity}  -> "Live Progress View"
task.started / task.completed / task.failed
prompt.created
generation.queued / generation.progress / generation.completed
image.created             // {asset_id, image_id, url}  -> live image appears
review.started / review.completed   // {verdict, scores}
asset.state_changed       // {asset_id, from, to}
scene.completed / act.completed
needs_director            // {asset_id, reason}  -> prompt the human
director.command_applied  // {command}
budget.exhausted
```

**Notifications** = a curated subset (`task.completed`, `image.created` for
approvals, `review.completed`, `*.completed`, `needs_director`,
`budget.exhausted`). Each has read/unread state. The frontend toasts new
ones and lists them in the Notification center.

**Live Progress View** is built from the latest `agent.activity` per agent,
e.g.:
```
Writer Agent:       Analyzing Scene 4
Art Director:       Generating environment prompts
Critic Agent:       Reviewing Afghan rooftop references
Asset Manager:      Organizing approved assets
```

---

## 9. Voice control pipeline

Goal: Director presses the mic, speaks a command, agents incorporate it and
keep working.

Flow:
```
[mic button] ─record→ audio blob ─POST /api/projects/{id}/command (audio)
  → backend: Whisper (or OpenAI transcription) → text
  → Command Parser (small LLM call): map free speech to a structured
    Director command + args
  → push to interrupt queue (consumed in loop step DRAIN_INTERRUPTS)
  → emit director.command_applied event (UI confirms it was heard)
```

Recognized intents (extensible; free text always allowed and passed to the
Producer as a natural-language steer):
```
PAUSE                 "pause project"
RESUME                "continue project"
FOCUS {target}        "focus on environments"
GENERATE_MORE {target}"generate more references"
SET_STYLE {style}     "change style to …"
APPROVE_BATCH         "approve current batch"
REJECT {target}       "redo the Afghan camp"
REBUILD {character}   "rebuild Major P"
COMMENT {text}        anything else -> Producer takes it as guidance
```

Text commands use the same endpoint/parser (just skip transcription), so the
chat box and the mic produce identical structured commands. Optional upgrade:
OpenAI Realtime API for streaming voice + spoken status back. MVP = press,
speak, release, transcribe.

---

## 10. ComfyUI integration

ComfyUI runs **externally**; the backend talks to it over HTTP/WS at
`COMFYUI_URL`. Build a `ComfyUIClient`:

```
submit(workflow_json, prompt_inputs) -> prompt_id         POST /prompt
poll/stream progress                  -> %                WS /ws
fetch history(prompt_id)              -> outputs           GET /history/{id}
download image(filename, subfolder)   -> bytes             GET /view
```

Responsibilities:
- Hold **workflow templates** (JSON) in `backend/comfy/workflows/` — at
  least one txt2img reference workflow. The Art Director fills node inputs
  (positive, negative, seed, steps, cfg, dims, LoRA) from the Prompt record.
- **Queue monitoring:** translate ComfyUI progress into `generation.progress`
  events.
- **Image retrieval:** download outputs, push to MinIO, create `Image`
  records with full **metadata + seed tracking** (so generations are
  reproducible).
- Handle multiple images per prompt, errors, and timeouts (backoff).

Make the image backend swappable: a `txt2img` port with a ComfyUI
implementation now, leaving room for a hosted image API later (the
Director's "GPT generates images" can also map to a hosted image model via
the same port).

---

## 11. Frontend (Next.js + TypeScript + Tailwind + shadcn/ui)

### 11.1 Layout
- **Left sidebar (persistent):** Overview · Story · Characters ·
  Environments · Props · Storyboards · Animations · Tasks · Notifications ·
  Settings. (Storyboards/Animations show a "coming soon" badge in Phase 1.)
- **Top bar:** project name, **RUNNING/PAUSED** status pill with
  pause/resume, **mic button** (voice), notification bell with unread count,
  a text command box.
- **Main panel:** the selected view.
- A global **WebSocket client** subscribes to `/api/ws/projects/{id}` and
  feeds a store (Zustand or React Query + WS) that powers live updates,
  toasts, and the progress view.

### 11.2 Key views
- **Overview / Live Progress:** the "Current Agent Activity" board (§8),
  current task queue, recent events, project roadmap, budget meter.
- **Environments (the marquee drill-down):**
  - List of environments ("places"): Afghan Camp, Munich Apartment, Syrian
    Border Center, Psychiatric Ward, …, each with a thumbnail + state badge.
  - Click a place → detail page showing: **Description**, **References**,
    **Prompt history** (each prompt version, who wrote it, params, seed),
    **Generated images** in a gallery with per-image **state badge**
    (UNDER_REVIEW / APPROVED / REJECTED) and the **Critic's review** (scores
    + notes) inline, **Approval state**, **Related scenes**.
  - Director controls on each image: Approve / Reject (with note) /
    Regenerate; edit the description/brief.
  - **Live:** when a new image for this place is generated, it streams in
    with a "generating…" placeholder → resolves to the image → review badge
    appears. This is the "see the image being generated" requirement.
- **Characters:** biography, reference images, LoRA dataset, prompt history,
  relationships, costume variants, emotional states. Same image/approval UX.
- **Props:** description, refs, prompts, images, reviews.
- **Story:** screenplay reader, scene list, shot list, continuity notes.
- **Tasks:** the queue with states, owners, priorities, retries; filter by
  agent/state.
- **Notifications:** chronological center with read/unread, click → jumps to
  the related asset.
- **Settings:** provider→agent mapping, model IDs, approval thresholds,
  budgets, ComfyUI URL, style bible.

### 11.3 UX rules
- Every asset card shows its **state badge** with consistent colors.
- New events animate in; never require a manual refresh.
- Approve/Reject/Regenerate give instant optimistic feedback then reconcile
  with the server event.

---

## 12. Repository structure

```
movieai/
├── README.md
├── docs/
│   ├── BUILD_SPEC.md          ← this file
│   └── AGENTS.md              ← agent system prompts + tools
├── seed/
│   ├── story.md              ← the source story (Lili Marleen – Damascus)
│   └── character_bible.md    ← Major P, Lieutenant LM, style notes
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, routers, WS hub
│   │   ├── api/               routers (projects, assets, commands, ws)
│   │   ├── models/            SQLAlchemy models + enums (states)
│   │   ├── schemas/           Pydantic
│   │   ├── db/                session, Alembic migrations
│   │   ├── events/            event bus (publish→WS + persist)
│   │   ├── providers/         OpenAI / Anthropic / Google adapters
│   │   ├── agents/            director, writer, art_director, critic, asset_mgr
│   │   ├── orchestrator/      LangGraph loop, scheduler, budget guard
│   │   ├── comfy/             ComfyUIClient + workflows/*.json
│   │   ├── voice/             transcription + command parser
│   │   └── storage/           MinIO + Qdrant clients
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── app/                   Next.js app-router pages (per §11.2)
│   ├── components/            sidebar, cards, gallery, progress board, mic
│   ├── lib/                   api client, ws client, store
│   ├── package.json
│   └── tailwind.config.ts
└── scripts/
    └── seed_project.py        creates the seed project + the top instruction
```

---

## 13. Environment & secrets (`.env.example`)

```
# --- Provider keys (the Director's three keys) ---
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# --- Model IDs (upgradeable without code changes) ---
OPENAI_MODEL=gpt-...            # Director/Producer + Art Director
ANTHROPIC_MODEL=claude-...      # Writer
GOOGLE_MODEL=gemini-...         # Critic (multimodal)
TRANSCRIBE_MODEL=whisper-...    # voice

# --- Image generation ---
COMFYUI_URL=http://localhost:8188

# --- Infra ---
DATABASE_URL=postgresql+psycopg://movie:movie@postgres:5432/movieai
QDRANT_URL=http://qdrant:6333
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=movieai

# --- App ---
API_TOKEN=change-me
TICK_MS=2000
MAX_CONCURRENT_GENERATIONS=2
MAX_GENERATION_RETRIES=3
DAILY_TOKEN_BUDGET=2000000
DAILY_GENERATION_BUDGET=500
APPROVAL_MIN_BRIEF_MATCH=7
APPROVAL_MIN_STYLE=7
```

The build agent must **never** commit a real `.env`. Only `.env.example`.

---

## 14. Local dev / Docker Compose

`docker-compose.yml` brings up `postgres`, `qdrant`, `minio`, `backend`,
`frontend`. ComfyUI is external (point `COMFYUI_URL` at it). Provide:
- `make up` / `docker compose up` → full stack.
- Backend auto-runs Alembic migrations on start.
- `scripts/seed_project.py` → creates the seed project from `seed/` and sets
  the instruction *"Make an AI movie out of this comic/story in Waltz with
  Bashir style."*
- A `README.md` quickstart: copy `.env.example`→`.env`, add keys, `up`, open
  the dashboard, press **Start**, watch it work.

---

## 15. Build milestones (do in order; commit after each)

**M0 — Scaffold.** Repo structure (§12), docker-compose, env, healthcheck
endpoints, empty Next.js dashboard shell with the left nav. *Done when:*
`docker compose up` serves backend `/docs` and the frontend shell.

**M1 — Data + events.** All models/enums/migrations (§6), the event bus +
WS hub (§8), notifications. *Done when:* creating a project and forcing a
fake state transition pushes an event to a connected WS client and appears
in notifications.

**M2 — Providers + Writer.** Provider adapters (§5.1). Writer agent analyzes
`seed/story.md` → screenplay + scenes + shots + character/environment/prop
**briefs**, persisted and visible in the Story view. *Done when:* hitting
Start produces a screenplay and a populated tree for the seed story.

**M3 — Art Director + ComfyUI.** Art Director turns briefs into Prompt
records; `ComfyUIClient` generates images; images land in MinIO with seed
metadata; `image.created` events stream; images appear live in the
Environments/Characters detail views. *Done when:* an environment shows a
generated reference image that streamed in live.

**M4 — Critic loop.** Critic reviews each image (§5.4); APPROVED/REJECTED
with scores shown inline; rejects trigger a bounded prompt iteration +
regenerate; exhausted retries → NEEDS_DIRECTOR + notification. *Done when:*
the autonomous loop generates → reviews → iterates → approves without human
input, end to end, for the seed environments.

**M5 — Orchestrator autonomy.** LangGraph continuous loop (§5.3) with
Director/Producer planning, dependencies, pause/resume, checkpointing,
budget guard. *Done when:* one Start produces environments → characters →
props → shot list across multiple scenes, runs unattended, survives a
backend restart mid-run, and respects pause/resume.

**M6 — Human-in-the-loop + voice.** Text command box + mic button →
transcription → command parser → interrupt queue → applied next tick, with
`director.command_applied` confirmation. Director approve/reject/edit/
regenerate on any asset. *Done when:* speaking *"focus on environments"*
visibly reshuffles the queue, and *"pause project"* pauses it.

**M7 — Polish.** Live progress board, budget meter, asset state colors,
notification deep-links, settings (provider mapping, thresholds, budgets,
ComfyUI URL, style bible), Storyboards/Animations "coming soon" stubs.

Phase 2 (out of MVP scope, leave stubs): storyboard assembly, animation,
voice synthesis, music, editing timeline, trailer.

---

## 16. The seed task (what it should actually produce first)

On `Start`, the system must, for *Lili Marleen – Damascus* (Waltz-with-Bashir
style), autonomously:
1. Produce the screenplay + scene breakdown + shot list (9 chapters → scenes).
2. Build character bibles for **Major P** and **Lieutenant LM (Lili
   Marleen)** with reference images across costume/emotion variants.
3. Build environment bibles + references for at least: **Afghan Camp
   (Kunduz)**, **Munich Apartment**, **Syrian Border Center**, **Psychiatric
   Ward**.
4. Generate, review, iterate, and approve reference images for the above —
   each one visible in its drill-down with prompt history + Critic verdict.
5. Stream the whole thing as live progress + notifications, and obey Director
   interrupts.

See `seed/story.md` and `seed/character_bible.md` for the content.

---

## 17. Definition of done (every milestone)

- Code runs via `docker compose up` from a clean clone with `.env` filled.
- New behavior is reachable from the UI **and** emits the right events.
- No secrets committed; keys read from env.
- State changes go through the state machine and are persisted.
- The autonomy loop remains pausable, resumable, and restart-safe.
- README quickstart still works.
```
