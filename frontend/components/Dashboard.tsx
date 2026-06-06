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
  TriangleAlert,
  UserRound,
  Wand2,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Asset, EventRecord, Phase, Project, ProjectState, Scene, Task, api, bootProject, getApiBase } from "@/lib/api";

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
  AWAITING_APPROVAL: "state planning",
  COMPLETED: "state approved",
  TODO: "state draft",
  PLANNING: "state planning",
  PROPOSED: "state planning",
  GENERATING: "state generating",
  REVIEWING: "state review",
  UNDER_REVIEW: "state review",
  REJECTED: "state rejected",
  FAILED: "state rejected",
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    bootProject()
      .then(async (created) => {
        setProject(created);
        await refresh(created);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

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

  async function run<T>(fn: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh(project);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const start = () => project && run(() => api.start(project.id));
  const approvePhase = (phase: Phase) => run(() => api.approvePhase(phase.id));
  const rejectPhase = (phase: Phase) => run(() => api.rejectPhase(phase.id, "Director held this phase."));

  async function togglePause() {
    if (!project) return;
    await run(() => (project.status === "RUNNING" ? api.pause(project.id) : api.resume(project.id)));
  }

  async function sendCommand() {
    if (!project || !command.trim()) return;
    const text = command.trim();
    setCommand("");
    await run(() => api.command(project.id, text));
  }

  async function assetAction(kind: "approve" | "reject" | "regenerate", asset: Asset) {
    await run(() => {
      if (kind === "approve") return api.approve(asset.id);
      if (kind === "reject") return api.reject(asset.id, "Director requested another pass.");
      return api.regenerate(asset.id);
    });
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
            <h1>{project?.name ?? "Lili Marleen - Damascus"}</h1>
            <p>{project?.style ?? "Waltz with Bashir style bible"}</p>
          </div>
          <div className="top-actions">
            <span className={stateClass[project?.status ?? "DRAFT"]}>{(project?.status ?? "DRAFT").replace("_", " ")}</span>
            <button className="icon-button" onClick={togglePause} title={project?.status === "RUNNING" ? "Pause project" : "Resume project"}>
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

        {error ? (
          <section className="empty-state">
            <h2>Something needs attention</h2>
            <p>{error}</p>
          </section>
        ) : (
          <section className="content">{renderView()}</section>
        )}
      </main>
    </div>
  );

  function renderView() {
    if (view === "Overview")
      return <Overview state={state} latestImages={latestImages} busy={busy} onStart={start} onApprove={approvePhase} onReject={rejectPhase} />;
    if (view === "Story") return <Story screenplay={screenplay} scenes={scenes} />;
    if (view === "Characters" || view === "Environments" || view === "Props") {
      return <AssetWorkspace title={view} assets={assets} selectedAsset={selectedAsset} busy={busy} onSelect={setSelectedAssetId} onAction={assetAction} />;
    }
    if (view === "Tasks") return <Tasks state={state} />;
    if (view === "Notifications") return <Notifications events={state?.events ?? []} />;
    if (view === "Settings") return <SettingsView />;
    return <ComingSoon label={view} />;
  }
}

function PhasePanel({
  state,
  busy,
  onStart,
  onApprove,
  onReject
}: {
  state: ProjectState | null;
  busy: boolean;
  onStart: () => void;
  onApprove: (phase: Phase) => void;
  onReject: (phase: Phase) => void;
}) {
  const phase = state?.current_phase ?? null;
  const status = state?.project.status;
  const phaseTasks = (state?.tasks ?? []).filter((task) => task.phase_id === phase?.id);

  return (
    <section className="panel phase-panel">
      <div className="panel-head">
        <div>
          <h2>Production Pipeline</h2>
          <p>Approve each phase to let the agents generate it, then review the next.</p>
        </div>
      </div>

      {!phase && status !== "COMPLETED" && (
        <div className="phase-cta">
          <p>Press start and the Producer proposes the first phase as a checklist. Nothing is generated until you approve it.</p>
          <button className="primary" disabled={busy} onClick={onStart}><Play size={16} /> {busy ? "Working…" : "Start production"}</button>
        </div>
      )}

      {!phase && status === "COMPLETED" && (
        <div className="phase-cta">
          <p>All phases complete. Every reference has been generated and reviewed.</p>
        </div>
      )}

      {phase && (
        <div className="phase-active">
          <div className="phase-title">
            <span className="phase-no">Phase {phase.phase_no}</span>
            <strong>{phase.title}</strong>
            <span className={stateClass[phase.status]}>{phase.status}</span>
          </div>
          <p className="phase-desc">{phase.description}</p>

          {phase.status === "FAILED" && (
            <div className="phase-error">
              <TriangleAlert size={16} />
              <span>{String((phase.result as { error?: string })?.error ?? "This phase failed.")}</span>
            </div>
          )}

          <h3>{phase.status === "PROPOSED" || phase.status === "FAILED" ? "Planned tasks" : "Tasks"}</h3>
          <ol className="plan-list">
            {phase.plan.map((item) => {
              const task = phaseTasks.find((t) => t.payload.label === item.label);
              const taskStatus = task?.status;
              return (
                <li key={item.key + item.label}>
                  <span className={cx("plan-dot", taskStatus && stateClass[taskStatus])} />
                  <span className="plan-label">{item.label}</span>
                  {item.kind && <small className="plan-kind">{item.kind}</small>}
                  {taskStatus && <span className={stateClass[taskStatus]}>{taskStatus}</span>}
                </li>
              );
            })}
          </ol>

          {(phase.status === "PROPOSED" || phase.status === "FAILED") && (
            <div className="button-row">
              <button className="primary" disabled={busy} onClick={() => onApprove(phase)}>
                <Check size={16} /> {busy ? "Working…" : phase.status === "FAILED" ? "Retry phase" : "Approve & start"}
              </button>
              <button disabled={busy} onClick={() => onReject(phase)}><X size={16} /> Hold</button>
            </div>
          )}

          {(phase.status === "RUNNING" || phase.status === "REVIEWING") && (
            <p className="phase-working">Agents are working on this phase…</p>
          )}
        </div>
      )}

      <h3>Pipeline</h3>
      <div className="phase-stepper">
        {(state?.phases ?? []).map((p) => (
          <div key={p.id} className={cx("step", p.id === phase?.id && "current")}>
            <span className={stateClass[p.status]}>{p.phase_no}</span>
            <div>
              <strong>{p.title}</strong>
              <small>{p.status}</small>
            </div>
          </div>
        ))}
        {(state?.phases ?? []).length === 0 && <p className="phase-desc">No phases yet.</p>}
      </div>
    </section>
  );
}

function Overview({
  state,
  latestImages,
  busy,
  onStart,
  onApprove,
  onReject
}: {
  state: ProjectState | null;
  latestImages: { asset: Asset; image: Asset["images"][number] }[];
  busy: boolean;
  onStart: () => void;
  onApprove: (phase: Phase) => void;
  onReject: (phase: Phase) => void;
}) {
  const counts = state?.counts ?? {};
  return (
    <div className="overview-grid">
      <PhasePanel state={state} busy={busy} onStart={onStart} onApprove={onApprove} onReject={onReject} />
      <section className="panel">
        <h2>Production Counts</h2>
        <div className="metric-grid">
          {["scenes", "environments", "characters", "props", "phases", "tasks"].map((key) => (
            <div className="metric" key={key}>
              <strong>{counts[key] ?? 0}</strong>
              <span>{key}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="panel gallery-panel">
        <h2>Generated References</h2>
        {latestImages.length === 0 && <p className="phase-desc">References appear here once the reference phase is approved. Open Characters / Environments / Props to drill in.</p>}
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

function AssetWorkspace({ title, assets, selectedAsset, busy, onSelect, onAction }: { title: string; assets: Asset[]; selectedAsset?: Asset; busy: boolean; onSelect: (id: string) => void; onAction: (kind: "approve" | "reject" | "regenerate", asset: Asset) => void }) {
  return (
    <div className="asset-workspace">
      <section className="panel asset-list">
        <h2>{title}</h2>
        {assets.length === 0 && <p className="phase-desc">Nothing here yet. Approve the breakdown phase to populate {title.toLowerCase()}.</p>}
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
              <p className="brief">{selectedAsset.brief || "Brief is written when the Creative Briefs phase is approved."}</p>
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
                <button disabled={busy} onClick={() => onAction("approve", selectedAsset)}><Check size={16} /> Approve</button>
                <button disabled={busy} onClick={() => onAction("reject", selectedAsset)}><X size={16} /> Reject</button>
                <button disabled={busy} onClick={() => onAction("regenerate", selectedAsset)}><RefreshCcw size={16} /> Regenerate</button>
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
        <p className="screenplay">{screenplay || "The screenplay is written when the Story & Breakdown phase is approved."}</p>
      </section>
      <section className="panel">
        <h2>Scene Breakdown</h2>
        {scenes.length === 0 && <p className="phase-desc">No scenes yet.</p>}
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
      {(state?.tasks ?? []).length === 0 && <p className="phase-desc">Tasks appear as phases run.</p>}
      {(state?.tasks ?? []).map((task) => (
        <div className="task-row wide" key={task.id}>
          <span className={stateClass[task.status]}>{task.status}</span>
          <div>
            <strong>{task.payload.label ?? task.type}</strong>
            <p>{task.owner_agent} · retries {task.retries}</p>
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
        ["Producer / Art Director", "OpenAI", "gpt-4.1"],
        ["Writer", "Anthropic", "claude-3-7-sonnet-latest"],
        ["Critic", "Google", "gemini-2.5-pro"],
        ["Image backend", "ComfyUI", "http://localhost:8188"]
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
