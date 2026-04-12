'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles, UserCircle } from 'lucide-react';
import { Message } from 'ai';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6 px-4 md:px-0`}>
      <div className={`flex flex-col max-w-[85%] md:max-w-[75%] gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
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
            <div className="prose prose-slate prose-p:leading-relaxed prose-pre:bg-slate-900 prose-pre:text-slate-50 prose-a:text-blue-600 w-full max-w-none text-[15px]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content || '...'}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}