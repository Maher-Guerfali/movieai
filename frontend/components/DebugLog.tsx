"use client";

import { Bug, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { LogEntry, clearLogs, getLogs, subscribeLogs } from "@/lib/logger";

export default function DebugLog() {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<LogEntry[]>(getLogs());
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => subscribeLogs(setEntries), []);
  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight });
  }, [entries, open]);

  const errorCount = entries.filter((e) => e.level === "error").length;

  return (
    <div className="debug-dock">
      {open ? (
        <div className="debug-panel">
          <header className="debug-head">
            <strong><Bug size={14} /> Debug Log</strong>
            <div className="debug-head-actions">
              <button onClick={clearLogs} title="Clear"><Trash2 size={14} /></button>
              <button onClick={() => setOpen(false)} title="Close"><X size={14} /></button>
            </div>
          </header>
          <div className="debug-body" ref={bodyRef}>
            {entries.length === 0 && <p className="debug-empty">No log entries yet. API requests will appear here.</p>}
            {entries.map((e) => (
              <div key={e.id} className={`debug-row ${e.level}`}>
                <span className="debug-ts">{e.ts}</span>
                <div className="debug-msg">
                  <span>{e.message}</span>
                  {e.detail && <pre>{e.detail}</pre>}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <button className={`debug-fab ${errorCount ? "has-errors" : ""}`} onClick={() => setOpen(true)} title="Open debug log">
          <Bug size={16} />
          <span>Debug{errorCount ? ` (${errorCount})` : ""}</span>
        </button>
      )}
    </div>
  );
}
