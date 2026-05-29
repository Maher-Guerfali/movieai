# AI Movie Studio 🎬

An **autonomous AI movie production studio**. Feed it a comic + story and one
instruction — *"make me an AI movie out of this comic"* — and a team of AI
agents runs **continuously** to write the screenplay, design the characters
and environments, generate images, review them, and push the production
forward. You (the **Director**) watch live progress, get notifications, see
images appear, and **interrupt by voice or text** anytime to steer it.

> This repo currently contains the **build specification** — a complete brief
> you can hand to Claude Code or Codex to generate the actual application.
> Start with [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md).

## What it does

- **3 AI agents, 3 keys:** **GPT** owns visuals/image generation, **Claude**
  owns story + technical, **Gemini** reviews and critiques. They run in a
  loop: Claude says what to make and writes the brief → GPT writes prompts
  and generates via ComfyUI → Gemini + the brief approve or reject → on
  reject the prompt iterates; on approve it moves to the next item.
- **Autonomous + always running.** One "Start" and it keeps producing:
  environments → characters → props → shots. Pausable, resumable,
  restart-safe.
- **Voice + text control.** Press the mic (or type) — *"focus on
  environments"*, *"pause project"*, *"rebuild Major P"* — agents hear it and
  adjust on the next tick.
- **Live progress + notifications.** Every step streams over WebSockets; you
  see images being generated in real time.
- **Drill-down dashboard.** Left nav → **Environments / Characters / Props /
  Story / Storyboards / Tasks / Notifications / Settings**. Click an
  environment → its "places" → a place → its description, prompt history,
  generated images, and the AI's approve/reject verdicts.

## How to use this brief

1. Read [`docs/BUILD_SPEC.md`](docs/BUILD_SPEC.md) — the full architecture,
   data model, API, agent loop, ComfyUI integration, frontend, and the
   ordered build milestones (M0–M7).
2. Read [`docs/AGENTS.md`](docs/AGENTS.md) — each agent's role, system
   prompt, tools, and outputs.
3. Hand both to your coding agent: *"Build the repository described in
   docs/BUILD_SPEC.md, milestone by milestone."*
4. The first production is seeded from [`seed/`](seed/) — the story
   *"Lili Marleen – Damascus"* (Waltz with Bashir style) and the character
   bible for **Major P** and **Lieutenant LM**.

## Repo contents

```
docs/BUILD_SPEC.md     ← the master build brief (start here)
docs/AGENTS.md         ← agent roles, prompts, tools
seed/story.md          ← the seed movie's story + scene/environment map
seed/character_bible.md← Major P & Lili Marleen look + variants
seed/story-source.txt  ← the original director's note (raw)
.env.example           ← keys + config layout (never commit real .env)
```

## Tech stack (target)

Next.js · TypeScript · Tailwind · shadcn/ui · FastAPI · PostgreSQL · Qdrant ·
MinIO · LangGraph · ComfyUI · WebSockets · Whisper · Docker Compose · GPT +
Claude + Gemini.
