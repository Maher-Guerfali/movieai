// Lightweight client-side logger.
// Logs to the browser console AND keeps an in-memory buffer that the on-screen
// Debug Log panel subscribes to, so you can see API requests/errors without
// opening devtools.

export type LogLevel = "info" | "warn" | "error";

export type LogEntry = {
  id: number;
  ts: string;
  level: LogLevel;
  message: string;
  detail?: string;
};

const MAX = 300;
let counter = 0;
const entries: LogEntry[] = [];
const listeners = new Set<(entries: LogEntry[]) => void>();

function stringify(detail: unknown): string | undefined {
  if (detail === undefined || detail === null) return undefined;
  if (typeof detail === "string") return detail;
  try {
    return JSON.stringify(detail, null, 2);
  } catch {
    return String(detail);
  }
}

function push(level: LogLevel, message: string, detail?: unknown) {
  const entry: LogEntry = {
    id: ++counter,
    ts: new Date().toISOString().slice(11, 23),
    level,
    message,
    detail: stringify(detail)
  };
  entries.push(entry);
  if (entries.length > MAX) entries.shift();

  const tag = "%c[MovieAI]";
  const color = level === "error" ? "color:#c0392b;font-weight:bold" : level === "warn" ? "color:#b8860b" : "color:#6f7650";
  const fn = level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  if (entry.detail) fn(tag, color, message, "\n", entry.detail);
  else fn(tag, color, message);

  listeners.forEach((l) => l([...entries]));
}

export const log = {
  info: (message: string, detail?: unknown) => push("info", message, detail),
  warn: (message: string, detail?: unknown) => push("warn", message, detail),
  error: (message: string, detail?: unknown) => push("error", message, detail)
};

export function getLogs(): LogEntry[] {
  return [...entries];
}

export function subscribeLogs(fn: (entries: LogEntry[]) => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function clearLogs(): void {
  entries.length = 0;
  listeners.forEach((l) => l([]));
}
