import { useState } from "react";
import type { Source } from "../lib/types";

interface Props {
  sources: Source[];
}

export default function SourceCard({ sources }: Props) {
  const [open, setOpen] = useState(false);

  if (!sources.length) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs text-gray-400 hover:text-gray-200 flex items-center gap-1 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        {sources.length} source{sources.length === 1 ? "" : "s"}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((s, i) => (
            <div
              key={i}
              className="border border-gray-700 rounded-lg p-3 bg-gray-800/50 text-xs"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-blue-400">
                  [Source {i + 1}]
                </span>
                <span className="text-gray-500">
                  score: {s.score.toFixed(3)}
                </span>
              </div>
              <div className="text-gray-400 mb-1">
                {s.notebook && <span>{s.notebook}</span>}
                {s.section && <span> › {s.section}</span>}
                {s.page && <span> › {s.page}</span>}
              </div>
              <p className="text-gray-300 line-clamp-3">{s.text_preview}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
