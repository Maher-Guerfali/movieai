"use client";

import {
  Bell,
  Boxes,
  Check,
  Clapperboard,
  Film,
  Image as ImageIcon,
  Mic,
  Pause,
  Play,
  RefreshCcw,
  Settings,
  Sparkles,
  SquarePen,
  UserRound,
  Wand2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AppSettings, Asset, EventRecord, Project, ProjectState, Scene, api, createProject, loadProject, getApiBase } from "@/lib/api";

type View = "Overview" | "Story" | "Characters" | "Environments" | "Props" | "Storyboards" | "Animations" | "Tasks" | "Notifications" | "Settings";

const nav: { label: View; icon: React.ElementType }[] = [
  { label: "Overview", icon: Film },
  { label: "Story", icon: SquarePen },
  { label: "Characters", icon: UserRound },
  { label: "Environments", icon: ImageIcon },
  { label: "Props", icon: Boxes },
  { label: "Storyboards", icon: Clapperboard },
  { label: "Animations", icon: Sparkles },
  { label: "Tasks", icon: Check },
  { label: "Notifications", icon: Bell },
  { label: "Settings", icon: Settings }
];

const stateClass: Record<string, string> = {
  APPROVED: "state approved",
  RUNNING: "state running",
  PAUSED: "state paused",
  DRAFT: "state draft",
  TODO: "state draft",
  PLANNING: "state planning",
  GENERATING: "state generating",
  UNDER_REVIEW: "state review",
  REJECTED: "state rejected",
  NEEDS_DIRECTOR: "state rejected",
  DONE: "state approved",
  IN_PROGRESS: "state generating"
};

function cx(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default function Dashboard() {
  const [project, setProject] = useState<Project | null>(null);
  const [state, setState] = useState<ProjectState | null>(null);
  const [view, setView] = useState<View>("Overview");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [screenplay, setScreenplay] = useState("");
  const [command, setCommand] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectStyle, setNewProjectStyle] = useState("");
  const [creating, setCreating] = useState(false);

  async function refresh(activeProject = project) {
    if (!activeProject) return;
    const nextState = await api.getState(activeProject.id);
    setState(nextState);
    setProject(nextState.project);

    if (view === "Environments") setAssets(await api.environments(activeProject.id));
    if (view === "Characters") setAssets(await api.characters(activeProject.id));
    if (view === "Props") setAssets(await api.props(activeProject.id));
    if (view === "Story") {
      setScenes(await api.scenes(activeProject.id));
      setScreenplay((await api.screenplay(activeProject.id)).screenplay);
    }
  }

  useEffect(() => {
    loadProject()
      .then(async (loaded) => {
        if (loaded) {
          setProject(loaded);
          await refresh(loaded);
        }
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  async function handleCreateProject() {
    if (!newProjectName.trim()) return;
    setCreating(true);
    try {
      const created = await createProject(newProjectName.trim(), newProjectStyle.trim());
      setProject(created);
      await refresh(created);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    if (!project) return;
    refresh(project).catch((err: Error) => setError(err.message));
  }, [view]);

  useEffect(() => {
    if (!project) return;
    const wsBase = getApiBase().replace(/^http/, "ws");
    const socket = new WebSocket(`${wsBase}/api/ws/projects/${project.id}`);
    socket.onmessage = () => refresh(project).catch(() => undefined);
    return () => socket.close();
  }, [project?.id]);

  const selectedAsset = useMemo(() => assets.find((asset) => asset.id === selectedAssetId) ?? assets[0], [assets, selectedAssetId]);
  const latestImages = useMemo(() => assets.flatMap((asset) => asset.images.map((image) => ({ asset, image }))).slice(0, 6), [assets]);

  async function start() {
    if (!project) return;
    const started = await api.start(project.id);
    setProject(started);
    await refresh(started);
  }

  async function togglePause() {
    if (!project) return;
    const next = project.status === "RUNNING" ? await api.pause(project.id) : await api.resume(project.id);
    setProject(next);
    await refresh(next);
  }

  async function sendCommand() {
    if (!project || !command.trim()) return;
    await api.command(project.id, command.trim());
    setCommand("");
    await refresh(project);
  }

  async function assetAction(kind: "approve" | "reject" | "regenerate", asset: Asset) {
    if (kind === "approve") await api.approve(asset.id);
    if (kind === "reject") await api.reject(asset.id, "Director requested another pass.");
    if (kind === "regenerate") await api.regenerate(asset.id);
    await refresh(project);
  }

  if (error) {
    return (
      <div className="studio-shell">
        <main className="workspace">
          <section className="empty-state">
            <h2>Backend is not running</h2>
            <p>Start the FastAPI server on port 8000, then refresh this dashboard. Details: {error}</p>
          </section>
        </main>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="studio-shell">
        <main className="workspace">
          <section className="empty-state">
            <h2>AI Movie Studio</h2>
            <p>No projects yet. Create your first project to get started.</p>
            <div className="create-project-form">
              <input
                placeholder="Project name (e.g. My Film)"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateProject()}
              />
              <input
                placeholder="Visual style (e.g. noir, animated, live action)"
                value={newProjectStyle}
                onChange={(e) => setNewProjectStyle(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateProject()}
              />
              <button className="primary" onClick={handleCreateProject} disabled={creating || !newProjectName.trim()}>
                <Play size={16} /> {creating ? "Creating…" : "Create Project"}
              </button>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="studio-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Wand2 size={20} /></div>
          <div>
            <strong>AI Movie Studio</strong>
            <span>autonomous production</span>
          </div>
        </div>
        <nav>
          {nav.map((item) => {
            const Icon = item.icon;
            const disabled = item.label === "Storyboards" || item.label === "Animations";
            return (
              <button key={item.label} className={cx("nav-item", view === item.label && "active")} onClick={() => setView(item.label)}>
                <Icon size={17} />
                <span>{item.label}</span>
                {disabled && <small>soon</small>}
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>{project.name}</h1>
            <p>{project.style}</p>
          </div>
          <div className="top-actions">
            <span className={stateClass[project.status]}>{project.status}</span>
            <button className="icon-button" onClick={togglePause} title={project.status === "RUNNING" ? "Pause project" : "Resume project"}>
              {project.status === "RUNNING" ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button className="icon-button" title="Voice command"><Mic size={17} /></button>
            <div className="command">
              <input value={command} onChange={(event) => setCommand(event.target.value)} onKeyDown={(event) => event.key === "Enter" && sendCommand()} placeholder="tell the agents what to do" />
              <button onClick={sendCommand}>Send</button>
            </div>
            <button className="icon-button" title="Notifications"><Bell size={17} /></button>
          </div>
        </header>

        <section className="content">{renderView()}</section>
      </main>
    </div>
  );

  function renderView() {
    if (view === "Overview") return <Overview state={state} latestImages={latestImages} onStart={start} />;
    if (view === "Story") return <Story screenplay={screenplay} scenes={scenes} />;
    if (view === "Characters" || view === "Environments" || view === "Props") {
      return <AssetWorkspace title={view} assets={assets} selectedAsset={selectedAsset} onSelect={setSelectedAssetId} onAction={assetAction} />;
    }
    if (view === "Tasks") return <Tasks state={state} />;
    if (view === "Notifications") return <Notifications events={state?.events ?? []} />;
    if (view === "Settings") return <SettingsView />;
    return <ComingSoon label={view} />;
  }
}

function Overview({ state, latestImages, onStart }: { state: ProjectState | null; latestImages: { asset: Asset; image: Asset["images"][number] }[]; onStart: () => void }) {
  const counts = state?.counts ?? {};
  return (
    <div className="overview-grid">
      <section className="panel progress-panel">
        <div className="panel-head">
          <h2>Current Agent Activity</h2>
          <button className="primary" onClick={onStart}><Play size={16} /> Start</button>
        </div>
        <div className="agent-list">
          {Object.entries(state?.activity ?? {}).map(([agent, activity]) => (
            <div className="agent-row" key={agent}>
              <span>{agent.replace("_", " ")}</span>
              <p>{activity}</p>
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <h2>Production Counts</h2>
        <div className="metric-grid">
          {["scenes", "environments", "characters", "props", "tasks", "notifications"].map((key) => (
            <div className="metric" key={key}>
              <strong>{counts[key] ?? 0}</strong>
              <span>{key}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel queue-panel">
        <h2>Queue Timeline</h2>
        {(state?.tasks ?? []).map((task) => (
          <div className="task-row" key={task.id}>
            <span className={stateClass[task.status]}>{task.status}</span>
            <div>
              <strong>{task.payload.label ?? task.type}</strong>
              <p>{task.owner_agent}</p>
            </div>
          </div>
        ))}
      </section>
      <section className="panel gallery-panel">
        <h2>Generated References</h2>
        <div className="thumb-grid">
          {latestImages.map(({ asset, image }) => (
            <figure key={image.id}>
              <img src={`${getApiBase()}${image.url}`} alt={asset.name} />
              <figcaption>{asset.name}</figcaption>
            </figure>
          ))}
        </div>
      </section>
    </div>
  );
}

function AssetWorkspace({ title, assets, selectedAsset, onSelect, onAction }: { title: string; assets: Asset[]; selectedAsset?: Asset; onSelect: (id: string) => void; onAction: (kind: "approve" | "reject" | "regenerate", asset: Asset) => void }) {
  return (
    <div className="asset-workspace">
      <section className="panel asset-list">
        <h2>{title}</h2>
        {assets.map((asset) => (
          <button key={asset.id} className={cx("asset-row", selectedAsset?.id === asset.id && "active")} onClick={() => onSelect(asset.id)}>
            <span className={stateClass[asset.state]}>{asset.state}</span>
            <strong>{asset.name}</strong>
            <p>{asset.description}</p>
          </button>
        ))}
      </section>
      {selectedAsset && (
        <section className="panel detail-panel">
          <div className="panel-head">
            <div>
              <h2>{selectedAsset.name}</h2>
              <p>{selectedAsset.description}</p>
            </div>
            <span className={stateClass[selectedAsset.state]}>{selectedAsset.state}</span>
          </div>
          <div className="detail-grid">
            <div>
              <h3>Creative Brief</h3>
              <p className="brief">{selectedAsset.brief}</p>
              <h3>Prompt History</h3>
              {selectedAsset.prompts.map((prompt) => (
                <div className="prompt-box" key={prompt.id}>
                  <strong>v{prompt.version} · seed {prompt.seed}</strong>
                  <p>{prompt.positive}</p>
                </div>
              ))}
            </div>
            <div>
              <h3>Generated Images</h3>
              <div className="image-stack">
                {selectedAsset.images.map((image) => (
                  <img key={image.id} src={`${getApiBase()}${image.url}`} alt={selectedAsset.name} />
                ))}
              </div>
              <div className="button-row">
                <button onClick={() => onAction("approve", selectedAsset)}><Check size={16} /> Approve</button>
                <button onClick={() => onAction("reject", selectedAsset)}><Pause size={16} /> Reject</button>
                <button onClick={() => onAction("regenerate", selectedAsset)}><RefreshCcw size={16} /> Regenerate</button>
              </div>
              <h3>Critic Review</h3>
              {selectedAsset.reviews.map((review) => (
                <div className="review-box" key={review.id}>
                  <span className={stateClass[review.verdict]}>{review.verdict}</span>
                  <p>{review.notes}</p>
                  <div className="score-line">
                    {Object.entries(review.scores).map(([key, value]) => <span key={key}>{key}: {value}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function Story({ screenplay, scenes }: { screenplay: string; scenes: Scene[] }) {
  return (
    <div className="story-grid">
      <section className="panel">
        <h2>Screenplay Seed</h2>
        <p className="screenplay">{screenplay || "Press Start to generate the screenplay seed."}</p>
      </section>
      <section className="panel">
        <h2>Scene Breakdown</h2>
        {scenes.map((scene) => (
          <div className="scene-row" key={scene.id}>
            <span>{scene.scene_no.toString().padStart(2, "0")}</span>
            <div>
              <strong>{scene.title}</strong>
              <p>{scene.summary}</p>
              <small>{scene.location} · {scene.time_of_day}</small>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}

function Tasks({ state }: { state: ProjectState | null }) {
  return (
    <section className="panel">
      <h2>Tasks</h2>
      {(state?.tasks ?? []).map((task) => (
        <div className="task-row wide" key={task.id}>
          <span className={stateClass[task.status]}>{task.status}</span>
          <div>
            <strong>{task.payload.label ?? task.type}</strong>
            <p>{task.owner_agent} · priority {task.priority} · retries {task.retries}</p>
          </div>
        </div>
      ))}
    </section>
  );
}

function Notifications({ events }: { events: EventRecord[] }) {
  return (
    <section className="panel">
      <h2>Notifications</h2>
      {events.map((event) => (
        <div className="event-row" key={event.id}>
          <span>{event.type}</span>
          <p>{event.actor}</p>
          <time>{new Date(event.created_at).toLocaleString()}</time>
        </div>
      ))}
    </section>
  );
}

function SettingsView() {
  const [settings, setSettings] = useState<AppSettings | null>(null);

  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => undefined);
  }, []);

  if (!settings) return <section className="panel"><p>Loading settings…</p></section>;

  const rows = [
    ["Producer / Art Director", "OpenAI", settings.openai_model, settings.openai_configured],
    ["Writer", "Anthropic", settings.anthropic_model, settings.anthropic_configured],
    ["Critic", "Google", settings.google_model, settings.google_configured],
    ["Image backend", "ComfyUI", settings.comfyui_url, !settings.use_mock_ai],
  ] as [string, string, string, boolean][];

  return (
    <section className="settings-grid">
      {rows.map(([agent, provider, model, configured]) => (
        <div className="panel setting" key={agent}>
          <span>{agent}</span>
          <strong>{provider}</strong>
          <p>{model}</p>
          <small className={configured ? "state approved" : "state draft"}>{configured ? "configured" : "not configured"}</small>
        </div>
      ))}
      {settings.use_mock_ai && (
        <div className="panel setting" style={{ gridColumn: "1 / -1" }}>
          <span>Mode</span>
          <strong>Mock AI</strong>
          <p>Set USE_MOCK_AI=false and provide API keys to enable real AI generation.</p>
        </div>
      )}
    </section>
  );
}

function ComingSoon({ label }: { label: string }) {
  return (
    <section className="empty-state">
      <h2>{label}</h2>
      <p>This phase is stubbed for the later storyboard, animation, audio, and timeline milestones.</p>
    </section>
  );
}
