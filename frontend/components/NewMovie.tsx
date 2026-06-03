"use client";

import { Clapperboard, Loader2 } from "lucide-react";
import { useState } from "react";
import { Project, createMovie } from "@/lib/api";

export default function NewMovie({ onCreated }: { onCreated: (project: Project) => void }) {
  const [name, setName] = useState("");
  const [style, setStyle] = useState("");
  const [idea, setIdea] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!idea.trim()) {
      setError("Describe your movie idea first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const project = await createMovie({
        name: name.trim() || "Untitled Movie",
        style: style.trim() || "cinematic animated film",
        idea: idea.trim()
      });
      onCreated(project);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="new-movie">
      <div className="new-movie-card">
        <div className="new-movie-head">
          <div className="brand-mark"><Clapperboard size={20} /></div>
          <div>
            <h2>Create a new movie</h2>
            <p>Describe your idea. The Writer agent turns it into a story, scenes and characters — then the studio generates everything.</p>
          </div>
        </div>

        <label>Movie title <small>(optional — the Writer can name it)</small></label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. The Last Lighthouse" disabled={busy} />

        <label>Visual style</label>
        <input value={style} onChange={(e) => setStyle(e.target.value)} placeholder="e.g. Studio Ghibli watercolor, warm light" disabled={busy} />

        <label>Movie idea / story</label>
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          rows={5}
          placeholder="Describe the plot, characters, mood… e.g. 'A retired lighthouse keeper discovers a stranded sea creature and must protect it from a coming storm and the townspeople who fear it.'"
          disabled={busy}
        />

        {error && <p className="new-movie-error">{error}</p>}

        <button className="primary new-movie-submit" onClick={submit} disabled={busy}>
          {busy ? <><Loader2 size={16} className="spin" /> Writing your movie…</> : <>Create movie</>}
        </button>
        <p className="new-movie-note">This calls GPT to write the story. If it fails, open the Debug log (bottom-right) to see exactly why.</p>
      </div>
    </div>
  );
}
