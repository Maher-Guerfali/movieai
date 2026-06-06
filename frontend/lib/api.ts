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

export type ProjectStatus = "DRAFT" | "AWAITING_APPROVAL" | "RUNNING" | "PAUSED" | "COMPLETED";

export type Project = {
  id: string;
  name: string;
  style: string;
  instruction: string;
  status: ProjectStatus;
  roadmap: Record<string, unknown>;
  counts: Record<string, number>;
};

export type PlanItem = {
  key: string;
  kind?: string;
  label: string;
  target_id?: string;
};

export type PhaseStatus = "PROPOSED" | "RUNNING" | "REVIEWING" | "DONE" | "REJECTED" | "FAILED";

export type Phase = {
  id: string;
  phase_no: number;
  key: string;
  title: string;
  description: string;
  status: PhaseStatus;
  plan: PlanItem[];
  result: Record<string, unknown>;
  created_at: string;
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
  phase_id?: string | null;
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

export type ProjectState = {
  project: Project;
  counts: Record<string, number>;
  phases: Phase[];
  current_phase: Phase | null;
  tasks: Task[];
  events: EventRecord[];
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
  if (projects[0]) return projects[0];
  return request<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify({
      name: "Lili Marleen - Damascus",
      style: "Waltz with Bashir - inked rotoscope, muted olive and sepia"
    })
  });
}

export const api = {
  getState: (projectId: string) => request<ProjectState>(`/api/projects/${projectId}/state`),
  start: (projectId: string) => request<Project>(`/api/projects/${projectId}/start`, { method: "POST" }),
  pause: (projectId: string) => request<Project>(`/api/projects/${projectId}/pause`, { method: "POST" }),
  resume: (projectId: string) => request<Project>(`/api/projects/${projectId}/resume`, { method: "POST" }),
  phases: (projectId: string) => request<Phase[]>(`/api/projects/${projectId}/phases`),
  approvePhase: (phaseId: string) => request<Phase>(`/api/phases/${phaseId}/approve`, { method: "POST" }),
  rejectPhase: (phaseId: string, notes: string) =>
    request<Phase>(`/api/phases/${phaseId}/reject`, { method: "POST", body: JSON.stringify({ notes }) }),
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
