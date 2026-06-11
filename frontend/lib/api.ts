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
  slug: string;
  title: string;
  summary: string;
  location: string;
  time_of_day: string;
  shots: { shot_no: number; description: string; camera: string; duration_s: number }[];
};

export type ProjectState = {
  project: Project;
  counts: Record<string, number>;
  tasks: Task[];
  events: EventRecord[];
  activity: Record<string, string>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function bootProject(): Promise<Project> {
  const projects = await request<Project[]>("/api/projects");
  let project = projects[0];
  if (!project) {
    project = await request<Project>("/api/projects", {
      method: "POST",
      body: JSON.stringify({
        name: "Lili Marleen - Damascus",
        style: "Waltz with Bashir - inked rotoscope, muted olive and sepia"
      })
    });
  }
  if (!project.counts?.scenes) {
    return request<Project>(`/api/projects/${project.id}/seed`, { method: "POST", body: JSON.stringify({}) });
  }
  return project;
}

export async function createSeedProject(): Promise<Project> {
  const project = await request<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify({
      name: "Lili Marleen - Damascus",
      style: "Waltz with Bashir - inked rotoscope, muted olive and sepia"
    })
  });
  return request<Project>(`/api/projects/${project.id}/seed`, { method: "POST", body: JSON.stringify({}) });
}

export const api = {
  getState: (projectId: string) => request<ProjectState>(`/api/projects/${projectId}/state`),
  start: (projectId: string) => request<Project>(`/api/projects/${projectId}/start`, { method: "POST" }),
  pause: (projectId: string) => request<Project>(`/api/projects/${projectId}/pause`, { method: "POST" }),
  resume: (projectId: string) => request<Project>(`/api/projects/${projectId}/resume`, { method: "POST" }),
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
  regenerate: (assetId: string) => request<Asset>(`/api/assets/${assetId}/regenerate`, { method: "POST" })
};
