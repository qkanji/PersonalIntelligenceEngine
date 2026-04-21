"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import {
  Sparkles,
  FileText,
  ChevronDown,
  ChevronUp,
  BookOpen,
} from "lucide-react";
import { Message } from "ai";

interface MessageBubbleProps {
  message: Message;
  streamData?: any[];
}

export function MessageBubble({ message, streamData }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const [showSources, setShowSources] = useState(false);

  // find sources from stream data that match this message or just grab the last one
  // if you sent it as { type: 'sources', messageId: message.id, sources: [...] }
  // but since we only care about displaying sources, we can try to extract from streamData
  const sourcesData = streamData?.filter((d) => d && d.type === "sources");

  // Since we append data continuously, let's find the sources block. Usually AI SDK binds it.
  // We'll just look for message.annotations if available, or fallback to the general parsed sources block.
  let sourcesList: string[] = [];
  if (message.annotations) {
    const ann = message.annotations.find((a: any) => a.type === "sources");
    if (ann) sourcesList = (ann as any).sources;
  } else if (sourcesData && sourcesData.length > 0) {
    // If not securely mapped, fallback to simple matching based on order or the latest block
    // (This is a simplified approach)
    sourcesList = sourcesData[sourcesData.length - 1].sources;
  }

  return (
    <div
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-6 px-4 md:px-0`}
    >
      <div
        className={`flex flex-col max-w-[85%] md:max-w-[75%] gap-2 ${isUser ? "items-end" : "items-start"}`}
      >
        {/* User bubble doesn't get fancy avatar, just solid color pill */}
        {isUser ? (
          <div className="bg-slate-100/80 rounded-3xl rounded-tr-sm px-5 py-3.5 text-[15px] leading-relaxed text-slate-800 shadow-sm border border-slate-200/50">
            {message.content}
          </div>
        ) : (
          <div className="flex items-start gap-4">
            <div className="mt-1 h-8 w-8 shrink-0 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-400 flex items-center justify-center shadow-md">
              <Sparkles className="h-4 w-4 text-white" />
            </div>
            <div className="flex flex-col gap-3 w-full">
              <div className="prose prose-slate prose-p:leading-relaxed prose-pre:bg-slate-900 prose-pre:text-slate-50 prose-a:text-blue-600 w-full max-w-none text-[15px]">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                >
                  {message.content || "..."}
                </ReactMarkdown>
              </div>

              {/* Optional Source Widget placeholder for future population based on annotations */}
              {!isUser &&
                message.content &&
                sourcesList &&
                sourcesList.length > 0 && (
                  <div className="flex flex-col gap-2 mt-3 block w-full max-w-md">
                    <div
                      onClick={() => setShowSources(!showSources)}
                      className="flex items-center justify-between w-fit gap-2 px-3 py-1.5 bg-indigo-50 border border-indigo-100 rounded-lg text-[13px] text-indigo-700/80 cursor-pointer hover:bg-indigo-100/80 transition-colors shadow-sm"
                    >
                      <div className="flex items-center gap-1.5 font-medium">
                        <FileText className="h-3.5 w-3.5" />
                        <span>
                          View Referenced Note Sources ({sourcesList.length})
                        </span>
                      </div>
                      {showSources ? (
                        <ChevronUp className="h-3.5 w-3.5 opacity-70" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5 opacity-70" />
                      )}
                    </div>

                    {showSources && (
                      <div className="flex flex-col gap-2 p-3 bg-white border border-slate-200/60 rounded-xl shadow-sm w-full animate-in fade-in slide-in-from-top-2 duration-200">
                        {sourcesList.map((src, i) => (
                          <div
                            key={i}
                            className="flex items-start gap-2 text-[12px] text-slate-600 bg-slate-50/80 p-2 rounded-md border border-slate-100/50"
                          >
                            <BookOpen className="h-3.5 w-3.5 mt-0.5 text-slate-400 shrink-0" />
                            <span className="break-words font-mono text-[11px] leading-relaxed">
                              {src.replace(".md", "").replace(/_/g, " > ")}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
