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

## Conversational Assistant + Mediator

A live chat assistant is docked in the **top-left** of the dashboard. It:

- Answers questions about the website and the current production (scenes,
  characters, environments, props, tasks, agent activity).
- Acts on your behalf: when you ask for a change, the **mediator agent** applies
  it to the shared production tree the always-on agents work from
  (pause/resume, change style, update an asset brief, regenerate / approve /
  reject an asset).

Backend pieces:

- `backend/app/providers/` — real `OpenAIProvider` and `GeminiProvider`, plus a
  `factory.get_provider()` that selects one from `.env` (falling back to the
  mock provider if no key is set).
- `backend/app/agents/assistant.py` — the conversational agent (returns a reply
  plus structured actions).
- `backend/app/agents/mediator.py` — applies those actions to the production tree.
- Endpoints: `POST /api/projects/{id}/chat` and `GET /api/projects/{id}/chat`.

## Mock vs. real AI

`USE_MOCK_AI` controls whether real provider keys are used. With the keys set in
`.env` and `USE_MOCK_AI=false` (the new default), the chat assistant and mediator
call GPT (or Gemini, via `DEFAULT_LLM_PROVIDER`). Set `USE_MOCK_AI=true` to run
the deterministic seed loop with no credentials.

> Note: the seed **writer / art_director / critic** loop still produces
> deterministic seed data and mock ComfyUI references. Wiring those to live
> models + a real ComfyUI workflow is the next milestone; the provider layer is
> now in place for it.

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
