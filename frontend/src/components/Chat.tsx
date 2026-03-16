import { useRef, useState, useEffect, type FormEvent } from "react";
import type { Message, Source } from "../lib/types";
import { streamChat } from "../lib/api";
import MessageBubble from "./MessageBubble";

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || streaming) return;

    // Add user message
    const userMsg: Message = { role: "user", content: text };
    const updatedHistory = [...messages, userMsg];
    setMessages(updatedHistory);
    setInput("");
    setStreaming(true);

    // Placeholder for assistant
    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages([...updatedHistory, assistantMsg]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      // Build history for API (only previous turns, not the current user message)
      const apiHistory = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      let accumulated = "";

      await streamChat(
        text,
        apiHistory,
        // onToken
        (token) => {
          accumulated += token;
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = {
              ...copy[copy.length - 1],
              content: accumulated,
            };
            return copy;
          });
        },
        // onSources
        (sources: Source[]) => {
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = {
              ...copy[copy.length - 1],
              sources,
            };
            return copy;
          });
        },
        controller.signal,
      );
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        // user cancelled — no-op
      } else {
        const errMsg = err instanceof Error ? err.message : "Unknown error";
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1] = {
            role: "assistant",
            content: `**Error:** ${errMsg}`,
          };
          return copy;
        });
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto">
      {/* Header */}
      <header className="flex-none border-b border-gray-800 px-4 py-3">
        <h1 className="text-lg font-semibold text-gray-100">
          Personal Intelligence Engine
        </h1>
        <p className="text-xs text-gray-500">
          RAG chatbot — your notes, your local LLM
        </p>
      </header>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-6 space-y-4"
      >
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">
            Ask a question about your notes…
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {/* Streaming dot indicator */}
        {streaming &&
          messages.length > 0 &&
          messages[messages.length - 1].content === "" && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3">
                <span className="inline-flex gap-1">
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:300ms]" />
                </span>
              </div>
            </div>
          )}
      </div>

      {/* Input bar */}
      <form
        onSubmit={handleSubmit}
        className="flex-none border-t border-gray-800 px-4 py-3 flex gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
          className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm 
                     text-gray-100 placeholder-gray-500 outline-none
                     focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
          disabled={streaming}
        />
        {streaming ? (
          <button
            type="button"
            onClick={handleStop}
            className="px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium
                       rounded-xl transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 
                       disabled:text-gray-500 text-white text-sm font-medium
                       rounded-xl transition-colors"
          >
            Send
          </button>
        )}
      </form>
    </div>
  );
}
