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
import { Asset, EventRecord, Project, ProjectState, Scene, api, bootProject, deleteProject, getApiBase } from "@/lib/api";
import ChatAssistant from "@/components/ChatAssistant";
import DebugLog from "@/components/DebugLog";
import NewMovie from "@/components/NewMovie";
import { log } from "@/lib/logger";

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
  const [booted, setBooted] = useState(false);

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
    log.info("Dashboard mounted. API base = " + getApiBase());
    bootProject()
      .then(async (existing) => {
        if (existing) {
          setProject(existing);
          await refresh(existing);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setBooted(true));
  }, []);

  // Poll state while the worker is running so usage/progress stays live even
  // if a WebSocket event is missed.
  useEffect(() => {
    if (!project) return;
    const id = setInterval(() => {
      refresh(project).catch((err: Error) => log.warn("poll refresh failed", err.message));
    }, 5000);
    return () => clearInterval(id);
  }, [project?.id, view]);

  async function onCreated(created: Project) {
    setProject(created);
    setError(null);
    await refresh(created);
  }

  async function startOver() {
    if (!project) return;
    if (!confirm("Delete this movie and start a new one?")) return;
    await deleteProject(project.id);
    setProject(null);
    setState(null);
    setAssets([]);
    setScenes([]);
    setScreenplay("");
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

  async function guard(action: () => Promise<void>) {
    try {
      await action();
      setError(null);
    } catch (err) {
      const message = (err as Error).message;
      log.error("Action failed", message);
      setError(message);
    }
  }

  async function start() {
    if (!project) return;
    await guard(async () => {
      const started = await api.start(project.id);
      setProject(started);
      await refresh(started);
    });
  }

  async function stop() {
    if (!project) return;
    await guard(async () => {
      const next = await api.pause(project.id);
      setProject(next);
      await refresh(next);
    });
  }

  async function togglePause() {
    if (!project) return;
    await guard(async () => {
      const next = project.status === "RUNNING" ? await api.pause(project.id) : await api.resume(project.id);
      setProject(next);
      await refresh(next);
    });
  }

  async function sendCommand() {
    if (!project || !command.trim()) return;
    await guard(async () => {
      await api.command(project.id, command.trim());
      setCommand("");
      await refresh(project);
    });
  }

  async function assetAction(kind: "approve" | "reject" | "regenerate", asset: Asset) {
    await guard(async () => {
      if (kind === "approve") await api.approve(asset.id);
      if (kind === "reject") await api.reject(asset.id, "Director requested another pass.");
      if (kind === "regenerate") await api.regenerate(asset.id);
      await refresh(project);
    });
  }

  if (!project) {
    return (
      <>
        <DebugLog />
        {booted ? (
          <NewMovie onCreated={onCreated} />
        ) : (
          <div className="boot-screen"><p>Connecting to the studio…</p></div>
        )}
      </>
    );
  }

  return (
    <div className="studio-shell">
      <DebugLog />
      <ChatAssistant projectId={project?.id} onActed={() => refresh(project).catch(() => undefined)} />
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
            {state?.usage && (
              <span className={cx("worker-dot", state.usage.worker_running && "live")} title={state.usage.worker_running ? "Agents running" : "Agents idle"}>
                {state.usage.worker_running ? "● live" : "○ idle"}
              </span>
            )}
            <button className="icon-button" onClick={startOver} title="Delete & start a new movie"><SquarePen size={17} /></button>
            <span className={stateClass[project?.status ?? "DRAFT"]}>{project?.status ?? "DRAFT"}</span>
            <button className="icon-button" onClick={togglePause} title={project?.status === "RUNNING" ? "Stop agents" : "Run agents"}>
              {project?.status === "RUNNING" ? <Pause size={17} /> : <Play size={17} />}
            </button>
            <button className="icon-button" title="Voice command"><Mic size={17} /></button>
            <div className="command">
              <input value={command} onChange={(event) => setCommand(event.target.value)} onKeyDown={(event) => event.key === "Enter" && sendCommand()} placeholder="tell the agents what to do" />
              <button onClick={sendCommand}>Send</button>
            </div>
            <button className="icon-button" title="Notifications"><Bell size={17} /></button>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <strong>Error:</strong> {error}
            <button onClick={() => setError(null)} title="Dismiss">✕</button>
          </div>
        )}
        <section className="content">{renderView()}</section>
      </main>
    </div>
  );

  function renderView() {
    if (view === "Overview") return <Overview state={state} latestImages={latestImages} onStart={start} onStop={stop} />;
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

function Overview({ state, latestImages, onStart, onStop }: { state: ProjectState | null; latestImages: { asset: Asset; image: Asset["images"][number] }[]; onStart: () => void; onStop: () => void }) {
  const counts = state?.counts ?? {};
  const usage = state?.usage;
  return (
    <div className="overview-grid">
      <section className="panel progress-panel">
        <div className="panel-head">
          <h2>Current Agent Activity</h2>
          {usage?.worker_running ? (
            <button className="primary stop" onClick={onStop}><Pause size={16} /> Stop</button>
          ) : (
            <button className="primary" onClick={onStart}><Play size={16} /> Run</button>
          )}
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

      {usage && (
        <section className="panel usage-panel">
          <h2>Usage Today <small className="usage-day">{usage.day}</small></h2>
          <div className="metric-grid">
            <div className="metric"><strong>{usage.tokens.toLocaleString()}</strong><span>tokens</span></div>
            <div className="metric"><strong>{usage.images}</strong><span>images</span></div>
            <div className="metric"><strong>${usage.cost_usd.toFixed(2)}</strong><span>est. cost</span></div>
            <div className="metric">
              <strong>{usage.generations_remaining ?? "∞"}</strong>
              <span>images left</span>
            </div>
          </div>
          {usage.token_budget > 0 && (
            <div className="usage-bar" title={`${usage.tokens} / ${usage.token_budget} tokens`}>
              <div className="usage-bar-fill" style={{ width: `${Math.min(100, (usage.tokens / usage.token_budget) * 100)}%` }} />
            </div>
          )}
          <p className="usage-note">Budgets are set in <code>.env</code> (DAILY_TOKEN_BUDGET / DAILY_GENERATION_BUDGET). Agents auto-pause when reached.</p>
        </section>
      )}
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
        <h2>Screenplay</h2>
        <p className="screenplay">{screenplay || "The Writer generated your story when the movie was created. If this is empty, check the Debug log."}</p>
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
  return (
    <section className="settings-grid">
      {[
        ["Art Director (prompts)", "OpenAI GPT", "gpt-4.1"],
        ["Critic (review)", "OpenAI GPT vision", "gpt-4.1"],
        ["Assistant + Mediator", "OpenAI GPT", "gpt-4.1"],
        ["Image generation", "OpenAI Images", "gpt-image-1"]
      ].map(([agent, provider, model]) => (
        <div className="panel setting" key={agent}>
          <span>{agent}</span>
          <strong>{provider}</strong>
          <p>{model}</p>
        </div>
      ))}
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
