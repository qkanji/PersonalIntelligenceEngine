import type { Source, Message } from "./types";

const API_BASE = "http://localhost:8000";

/**
 * Stream a chat response from the FastAPI backend.
 *
 * Calls `onToken` for every token chunk and `onSources` once with the
 * retrieval metadata when the stream ends.
 */
export async function streamChat(
  message: string,
  history: Pick<Message, "role" | "content">[],
  onToken: (token: string) => void,
  onSources: (sources: Source[]) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
    signal,
  });

  if (!res.ok) {
    throw new Error(`Backend error: ${res.status} ${res.statusText}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by double newlines
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;

      const payload = line.slice(6); // strip "data: "
      if (payload === "[DONE]") return;

      try {
        const evt = JSON.parse(payload);
        if (evt.type === "token") {
          onToken(evt.content);
        } else if (evt.type === "sources") {
          onSources(evt.content as Source[]);
        }
      } catch {
        // non-JSON payload — ignore
      }
    }
  }
}

/** Quick health check – returns the JSON body. */
export async function healthCheck(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}
