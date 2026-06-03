import { log } from "@/lib/logger";

declare global {
  interface Window {
    __MOVIEAI_CONFIG__?: {
      API_BASE_URL?: string;
    };
  }
}

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    return window.__MOVIEAI_CONFIG__?.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  }
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export type Project = {
  id: string;
  name: string;
  style: string;
  instruction: string;
  status: "DRAFT" | "RUNNING" | "PAUSED";
  roadmap: Record<string, unknown>;
  counts: Record<string, number>;
};

export type EventRecord = {
  id: string;
  type: string;
  actor: string;
  payload: Record<string, unknown>;
  read: boolean;
  created_at: string;
};

export type Task = {
  id: string;
  type: string;
  owner_agent: string;
  status: string;
  priority: number;
  payload: { label?: string };
  retries: number;
};

export type ImageRecord = {
  id: string;
  url: string;
  state: string;
  seed: number;
  width: number;
  height: number;
};

export type Review = {
  id: string;
  verdict: string;
  scores: Record<string, number>;
  issues: string[];
  notes: string;
};

export type Prompt = {
  id: string;
  positive: string;
  negative: string;
  seed: number;
  version: number;
  params: Record<string, unknown>;
};

export type Asset = {
  id: string;
  project_id: string;
  kind: "CHARACTER" | "ENVIRONMENT" | "PROP";
  name: string;
  description: string;
  brief: string;
  state: string;
  metadata_json: Record<string, unknown>;
  prompts: Prompt[];
  images: ImageRecord[];
  reviews: Review[];
};

export type Scene = {
  id: string;
  act_no: number;
  scene_no: number;
  title: string;
  summary: string;
  location: string;
  time_of_day: string;
  shots: { shot_no: number; description: string; camera: string; duration_s: number }[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  agent: string;
  content: string;
  actions: Array<Record<string, unknown>>;
  created_at: string;
};

export type ChatResponse = {
  reply: string;
  actions: Array<Record<string, unknown>>;
  messages: ChatMessage[];
};

export type Usage = {
  day: string;
  tokens: number;
  images: number;
  cost_usd: number;
  token_budget: number;
  generation_budget: number;
  tokens_remaining: number | null;
  generations_remaining: number | null;
  worker_running: boolean;
};

export type ProjectState = {
  project: Project;
  counts: Record<string, number>;
  usage?: Usage;
  tasks: Task[];
  events: EventRecord[];
  activity: Record<string, string>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = init?.method ?? "GET";
  const url = `${getApiBase()}${path}`;
  const started = performance.now();
  log.info(`→ ${method} ${path}`, init?.body ? safeParse(init.body) : undefined);

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
    });
  } catch (networkErr) {
    log.error(`✗ ${method} ${path} — network/CORS failure`, {
      message: (networkErr as Error).message,
      url,
      hint: "Is the backend running on " + getApiBase() + " ? Check CORS / FRONTEND_ORIGIN."
    });
    throw new Error(`Network error calling ${path}: ${(networkErr as Error).message}`);
  }

  const ms = Math.round(performance.now() - started);
  const raw = await response.text();
  let parsed: unknown = undefined;
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = raw;
    }
  }

  if (!response.ok) {
    const detail = (parsed as { detail?: unknown })?.detail ?? parsed ?? response.statusText;
    log.error(`✗ ${method} ${path} → ${response.status} (${ms}ms)`, detail);
    throw new Error(`${response.status} ${response.statusText} — ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }

  log.info(`✓ ${method} ${path} → ${response.status} (${ms}ms)`);
  return parsed as T;
}

function safeParse(body: BodyInit): unknown {
  if (typeof body !== "string") return "[binary body]";
  try {
    return JSON.parse(body);
  } catch {
    return body;
  }
}

/**
 * Returns the existing project, or null if none exists yet.
 * No static seed is created — the user creates a movie from their own idea.
 */
export async function bootProject(): Promise<Project | null> {
  const projects = await request<Project[]>("/api/projects");
  return projects[0] ?? null;
}

/** Create a brand-new movie project from a user-supplied idea, then seed it via GPT. */
export async function createMovie(input: { name: string; style: string; idea: string }): Promise<Project> {
  const project = await request<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify({ name: input.name, style: input.style })
  });
  return request<Project>(`/api/projects/${project.id}/seed`, {
    method: "POST",
    body: JSON.stringify({ instruction: input.idea })
  });
}

export async function deleteProject(projectId: string): Promise<void> {
  await request<{ deleted: boolean }>(`/api/projects/${projectId}`, { method: "DELETE" });
}

export const api = {
  getState: (projectId: string) => request<ProjectState>(`/api/projects/${projectId}/state`),
  start: (projectId: string) => request<Project>(`/api/projects/${projectId}/start`, { method: "POST" }),
  pause: (projectId: string) => request<Project>(`/api/projects/${projectId}/pause`, { method: "POST" }),
  resume: (projectId: string) => request<Project>(`/api/projects/${projectId}/resume`, { method: "POST" }),
  usage: (projectId: string) => request<Usage>(`/api/projects/${projectId}/usage`),
  command: (projectId: string, text: string) =>
    request<{ applied: boolean; status: string }>(`/api/projects/${projectId}/command`, {
      method: "POST",
      body: JSON.stringify({ text })
    }),
  environments: (projectId: string) => request<Asset[]>(`/api/projects/${projectId}/environments`),
  characters: (projectId: string) => request<Asset[]>(`/api/projects/${projectId}/characters`),
  props: (projectId: string) => request<Asset[]>(`/api/projects/${projectId}/props`),
  scenes: (projectId: string) => request<Scene[]>(`/api/projects/${projectId}/scenes`),
  screenplay: (projectId: string) => request<{ screenplay: string; roadmap: Record<string, unknown> }>(`/api/projects/${projectId}/screenplay`),
  approve: (assetId: string) => request<Asset>(`/api/assets/${assetId}/approve`, { method: "POST" }),
  reject: (assetId: string, notes: string) =>
    request<Asset>(`/api/assets/${assetId}/reject`, { method: "POST", body: JSON.stringify({ notes }) }),
  regenerate: (assetId: string) => request<Asset>(`/api/assets/${assetId}/regenerate`, { method: "POST" }),
  chatHistory: (projectId: string) => request<ChatMessage[]>(`/api/projects/${projectId}/chat`),
  chat: (projectId: string, text: string) =>
    request<ChatResponse>(`/api/projects/${projectId}/chat`, {
      method: "POST",
      body: JSON.stringify({ text })
    })
};
