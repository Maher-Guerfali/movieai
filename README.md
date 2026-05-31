# AI Movie Studio

An autonomous AI movie production studio for turning a comic/story package into a film production tree. The first seeded production is **Lili Marleen - Damascus**, in a restrained *Waltz with Bashir* inspired visual style.

This repo now contains a runnable MVP scaffold:

- FastAPI backend with project, scene, asset, prompt, image, review, task, event, and notification models.
- Deterministic mock agent loop for local development: Writer creates the seed story tree, Art Director creates prompts/mock image references, Critic approves with structured scores.
- WebSocket event hub and REST API under `/api`.
- Next.js dashboard with left navigation, live progress, task queue, story view, environment/character/prop drill-downs, prompt history, generated references, critic reviews, and Director controls.
- Docker Compose for Postgres, Qdrant, MinIO, backend, and frontend. ComfyUI remains an external configurable service.

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend OpenAPI: http://localhost:8000/docs

For a lightweight local run without Docker:

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend creates/seeds the first project automatically. Press **Start** to run the deterministic seed production loop.

## Current MVP Behavior

`USE_MOCK_AI=true` is the default. That means the app runs without GPT, Claude, Gemini, MinIO, or ComfyUI credentials and produces stable seed outputs for UI and orchestration development.

To connect real services, replace the provider stubs in `backend/app/providers/`, wire the ComfyUI workflow in `backend/app/comfy/workflows/`, and set the keys/URLs in `.env`.

## Repository Map

```text
backend/              FastAPI app, SQLAlchemy models, event hub, agents, ComfyUI client
frontend/             Next.js dashboard
docs/BUILD_SPEC.md    Original build specification
docs/AGENTS.md        Agent roles and system prompts
seed/                 Story and character bible for Lili Marleen - Damascus
scripts/seed_project.py
docker-compose.yml
```

## Seed Material

The first production is driven by:

- `seed/story.md`
- `seed/character_bible.md`
- `seed/story-source.txt`

The real reference sheets mentioned in the character bible should be added to `seed/refs/` when available.
