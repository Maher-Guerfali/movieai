"use client";

import { MessageCircle, Send, Sparkles, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ChatMessage, api } from "@/lib/api";

export default function ChatAssistant({ projectId, onActed }: { projectId?: string; onActed?: () => void }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!projectId || !open) return;
    api.chatHistory(projectId).then(setMessages).catch(() => undefined);
  }, [projectId, open]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  async function send() {
    const text = input.trim();
    if (!projectId || !text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", agent: "user", content: text, actions: [], created_at: new Date().toISOString() }
    ]);
    try {
      const res = await api.chat(projectId, text);
      setMessages(res.messages);
      if (res.actions.some((a) => (a as { ok?: boolean }).ok)) onActed?.();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          agent: "assistant",
          content: `Couldn't reach the assistant. Is the backend running? (${(err as Error).message})`,
          actions: [],
          created_at: new Date().toISOString()
        }
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="assistant-dock">
      {open ? (
        <div className="assistant-panel">
          <header className="assistant-head">
            <div className="assistant-title">
              <Sparkles size={16} />
              <div>
                <strong>Studio Assistant</strong>
                <span>ask about the website or tell the agents to make edits</span>
              </div>
            </div>
            <button className="assistant-close" onClick={() => setOpen(false)} title="Close">
              <X size={16} />
            </button>
          </header>

          <div className="assistant-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="assistant-hint">
                Try: <em>&quot;What scenes do we have?&quot;</em>, <em>&quot;Regenerate Major P&quot;</em>, or{" "}
                <em>&quot;Make the style darker and pause production.&quot;</em>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`assistant-msg ${m.role}`}>
                <p>{m.content}</p>
                {m.actions?.length > 0 && (
                  <ul className="assistant-actions">
                    {m.actions.map((a, i) => (
                      <li key={i}>
                        {(a as { ok?: boolean }).ok === false ? "⚠️ " : "✓ "}
                        {(a as { detail?: string; type?: string }).detail ?? (a as { type?: string }).type}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {busy && <div className="assistant-msg assistant typing">thinking…</div>}
          </div>

          <div className="assistant-input">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              placeholder="Ask or instruct the agents…"
              disabled={busy}
            />
            <button onClick={send} disabled={busy} title="Send">
              <Send size={16} />
            </button>
          </div>
        </div>
      ) : (
        <button className="assistant-fab" onClick={() => setOpen(true)} title="Open studio assistant">
          <MessageCircle size={18} />
          <span>Assistant</span>
        </button>
      )}
    </div>
  );
}
