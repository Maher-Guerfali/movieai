# AI Movie Studio

An autonomous AI movie production studio. You type a **movie idea**; the studio's
agents write the story, break it into scenes and assets, generate reference
images, and review them — live.

There is **no hardcoded story**. On first load you get a *Create a new movie*
form. The Writer agent (GPT) turns your idea into the title, screenplay, scenes,
and the character/environment/prop list. Then the always-on worker generates
prompts, images (OpenAI images API), and critic reviews for each asset.

Key pieces:

- FastAPI backend: project, scene, asset, prompt, image, review, task, event,
  chat, and usage models.
- Agents: `writer` (story from your idea), `art_director` (prompts), `critic`
  (image review), `assistant` + `mediator` (chat that edits the production).
- Always-on background worker; per-project usage tracking + budgets.
- WebSocket event hub and REST API under `/api`.
- Next.js dashboard: create-movie flow, live progress, usage panel, asset
  drill-downs, conversational assistant (top-left), and an on-screen **Debug
  Log** (bottom-right) that prints every API request/response and error.

## Troubleshooting ("it says running but nothing appears")

Open the **Debug Log** (bottom-right of the dashboard). It shows every API call,
the status code, timing, and the full error body from the backend — so you can
see exactly which request failed and why (bad/missing `OPENAI_API_KEY`, quota,
CORS, model name, etc.). The same logs are printed to the browser console
prefixed with `[MovieAI]`. Backend failures during story generation return a
clear `502` with the reason, and the worker pauses instead of spinning.

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
