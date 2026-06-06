# AI Movie Studio

An autonomous AI movie production studio for turning a comic/story package into a film production tree. The first seeded production is **Lili Marleen - Damascus**, in a restrained *Waltz with Bashir* inspired visual style.

This repo contains a runnable MVP:

- FastAPI backend with project, **phase**, scene, asset, prompt, image, review, task, event, and notification models.
- A **phase-gated production pipeline**: each phase is proposed as an itemized checklist and waits for Director approval before any generation happens. After it runs, it auto-reviews and proposes the next phase. See "How the loop works" below.
- **Real provider agents (no mock):** Writer → Anthropic Claude, Producer/Art Director → OpenAI GPT, Critic → Google Gemini (multimodal), images → ComfyUI. A phase that needs a key it doesn't have fails with a clear message instead of faking output.
- WebSocket event hub and REST API under `/api`.
- Next.js dashboard with the Production Pipeline panel (approve/hold each phase), live task progress, story view, environment/character/prop drill-downs, prompt history, generated references, critic reviews, and Director controls.
- Docker Compose for Postgres, Qdrant, MinIO, backend, and frontend. ComfyUI remains an external configurable service.

## How the loop works

1. Press **Start production**. The Producer proposes **Phase 1 (Story & Breakdown)** as a checklist — it generates nothing yet.
2. Review the planned tasks and press **Approve & start**. The Writer analyzes the seed story into a screenplay, scenes, and the list of environments/characters/props.
3. The phase auto-reviews and the next phase is proposed: **Creative Briefs**, then **Prompt Engineering**, then **Reference Images & Review** (each image is rendered and then automatically critiqued by Gemini).
4. You approve (or **Hold**) each phase until every reference, prompt, and review is done. The project then reports **COMPLETED**.

Every phase lists its tasks **per item** (e.g. one row per asset), so you always see exactly what is about to be generated before you approve it.

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

The frontend creates the first project automatically. Press **Start production** and approve phases as described above.

## Configuration (required)

There is **no mock mode** — the platform calls real providers. Set these in `.env`:

- `ANTHROPIC_API_KEY` — Writer (story breakdown + briefs).
- `OPENAI_API_KEY` — Producer / Art Director (image prompts).
- `GOOGLE_API_KEY` — Critic (multimodal image review).
- `COMFYUI_URL` + a real workflow graph at `backend/app/comfy/workflows/<COMFY_WORKFLOW>.json`.

The shipped `txt2img-reference.json` is a placeholder. Export an API-format ComfyUI graph and use the tokens `%positive%`, `%negative%`, `%seed%`, `%steps%`, `%cfg%`, `%width%`, `%height%` where those values should be injected. Until a real key/graph is present, the relevant phase will fail with a message telling you exactly what is missing.

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
