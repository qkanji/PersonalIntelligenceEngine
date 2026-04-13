'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useChat } from 'ai/react';
import { Sparkles, Image as ImageIcon, BookOpen, PenTool, SendHorizonal } from 'lucide-react';
import { NotebookPicker, NOTEBOOKS } from './NotebookPicker';
import { MessageBubble } from './MessageBubble';
import { Button } from '@/components/ui/button';

export default function Chat() {
  const [selectedNotebooks, setSelectedNotebooks] = useState<string[]>([...NOTEBOOKS]);
  
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: '/api/chat',
    body: {
      notebooks: selectedNotebooks
    }
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const hasMessages = messages.length > 0;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col h-full w-full relative pb-4 md:pb-6">
      {/* Top Header */}
      <header className="flex justify-between items-center py-2 px-2 md:px-0">
        <h1 className="text-xl font-semibold tracking-tight text-slate-800 flex items-center gap-2">
          PIE
        </h1>
        <NotebookPicker 
          selectedNotebooks={selectedNotebooks} 
          onChange={setSelectedNotebooks} 
        />
        {/* Placeholder avatar */}
        <div className="h-9 w-9 rounded-full bg-slate-200 border-2 border-white shadow-sm flex items-center justify-center font-bold text-slate-500 overflow-hidden text-sm">
          QK
        </div>
      </header>

      {/* Main Chat Area */}
      <div className="flex-1 overflow-y-auto mt-4 px-2 md:px-4 no-scrollbar">
        {!hasMessages ? (
          <div className="flex flex-col items-center justify-center h-full max-h-[60vh] mt-10 md:mt-20">
            <div className="w-full max-w-2xl px-4 lg:px-0 flex flex-col gap-6">
              <h2 className="text-[40px] leading-tight font-medium text-slate-700 font-sans tracking-tight mb-8">
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-500 to-indigo-500 font-semibold flex items-center gap-3">
                  <Sparkles className="h-8 w-8 text-indigo-500" />
                  Hi Qayim
                </span>
                <span className="text-slate-400 mt-1 block">Where should we start?</span>
              </h2>
            </div>
          </div>
        ) : (
          <div className="w-full max-w-3xl mx-auto pb-32">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {isLoading && (
              <div className="flex items-start gap-4 mb-6 px-4 md:px-0">
                <div className="mt-1 h-8 w-8 shrink-0 rounded-full bg-gradient-to-tr from-blue-500 to-indigo-400 flex flex-col items-center justify-center shadow-md animate-pulse">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div className="h-5 w-5 rounded-full bg-slate-200 animate-pulse mt-2 ml-1" />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Input Area */}
      <div className={`w-full max-w-3xl mx-auto transition-all duration-500 ease-in-out ${hasMessages ? 'absolute bottom-0 md:bottom-2 bg-white/80 backdrop-blur-xl border border-slate-100 p-2 md:p-3 rounded-[2rem] shadow-[0_-10px_40px_-15px_rgba(0,0,0,0.05)]' : 'px-4 lg:px-0'}`}>
        {!hasMessages && (
           <div className="w-full max-w-2xl mx-auto mb-6">
             <form 
               onSubmit={handleSubmit}
               className="relative flex items-center w-full bg-white border border-slate-200 shadow-sm hover:shadow-md transition-shadow rounded-[2rem] px-5 py-3 md:py-4 focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:border-indigo-400"
             >
               <input
                 className="flex-1 bg-transparent border-0 outline-none text-slate-800 text-[16px] placeholder:text-slate-400 placeholder:font-normal py-1 pr-12 min-h-12"
                 placeholder="Ask PIE anything about your notes..."
                 value={input || ''}
                 onChange={handleInputChange}
                 autoFocus
               />
               <button 
                 type="submit" 
                 disabled={!input?.trim()}
                 className="absolute right-3 p-2.5 rounded-full bg-slate-900 text-white disabled:bg-slate-100 disabled:text-slate-400 transition-colors"
               >
                 <SendHorizonal className="h-5 w-5" />
               </button>
             </form>

             {/* Style placeholder pills */}
             <div className="flex gap-3 justify-center md:justify-start mt-6 overflow-x-auto pb-2 no-scrollbar pl-2 md:pl-0">
               <Button variant="outline" className="rounded-full bg-white border-slate-200 text-slate-600 gap-2 h-11 px-5 shadow-sm font-normal">
                 <ImageIcon className="h-4 w-4 text-emerald-500" />
                 Create diagram
               </Button>
               <Button variant="outline" className="rounded-full bg-white border-slate-200 text-slate-600 gap-2 h-11 px-5 shadow-sm font-normal">
                 <BookOpen className="h-4 w-4 text-orange-500" />
                 Summarize notes
               </Button>
               <Button variant="outline" className="rounded-full bg-white border-slate-200 text-slate-600 gap-2 h-11 px-5 shadow-sm font-normal hidden sm:flex">
                 <PenTool className="h-4 w-4 text-blue-500" />
                 Test my knowledge
               </Button>
             </div>
           </div>
        )}

        {hasMessages && (
          <form 
            onSubmit={handleSubmit}
            className="flex items-center w-full bg-slate-50 border border-slate-200 rounded-[2rem] px-4 py-1.5 focus-within:ring-2 focus-within:ring-indigo-500/20"
          >
            <input
              className="flex-1 bg-transparent border-0 outline-none text-slate-800 text-[15px] placeholder:text-slate-400 py-3 pr-2"
              placeholder="Ask a follow-up question..."
              value={input || ''}
              onChange={handleInputChange}
            />
            <button 
              type="submit" 
              disabled={!input?.trim()}
              className="p-2 rounded-full hover:bg-slate-200 text-slate-800 disabled:opacity-50 transition-colors shrink-0"
            >
               <SendHorizonal className="h-5 w-5" />
            </button>
          </form>
        )}
      </div>
    </div>
  );
}