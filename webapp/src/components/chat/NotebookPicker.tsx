'use client';

import * as React from 'react';
import { ChevronDown, Check } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';

export const NOTEBOOKS = [
  "SNC1W - Science - c Notebook",
  "24-25 PPL1OM b - Healthy Active Living (Male) Notebook"
];

interface NotebookPickerProps {
  selectedNotebooks: string[];
  onChange: (notebooks: string[]) => void;
}

export function NotebookPicker({ selectedNotebooks, onChange }: NotebookPickerProps) {
  const toggleNotebook = (notebook: string) => {
    if (selectedNotebooks.includes(notebook)) {
      onChange(selectedNotebooks.filter((n) => n !== notebook));
    } else {
      onChange([...selectedNotebooks, notebook]);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="inline-flex shrink-0 items-center justify-center font-medium transition-all outline-none disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 gap-2 text-base max-w-[280px] sm:max-w-xs md:max-w-sm truncate text-slate-700 bg-white/50 backdrop-blur-md border border-slate-200/60 shadow-sm rounded-2xl hover:bg-slate-50 flex items-center justify-between">
          <span className="truncate">
            {selectedNotebooks.length === 0 
              ? "Select Notebooks" 
              : selectedNotebooks.length === 1 
                ? selectedNotebooks[0].split(' - ')[0] 
                : `${selectedNotebooks.length} Notebooks`}
          </span>
          <ChevronDown className="h-4 w-4 opacity-50 flex-none" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-[300px] p-2 rounded-2xl shadow-xl border-slate-200">
        <div className="px-2 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-widest">
          Filtered Metadata
        </div>
        <DropdownMenuSeparator className="my-1 border-slate-100" />
        {NOTEBOOKS.map((notebook) => {
          const isSelected = selectedNotebooks.includes(notebook);
          return (
            <DropdownMenuItem
              key={notebook}
              onSelect={(e) => {
                e.preventDefault();
                toggleNotebook(notebook);
              }}
              className="group flex items-start gap-3 p-2.5 rounded-xl cursor-default hover:bg-slate-50 outline-none"
            >
              <div
                className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border ${
                  isSelected
                    ? "border-blue-500 bg-blue-500 text-white"
                    : "border-slate-300 bg-transparent text-transparent"
                }`}
              >
                <Check className="h-3 w-3" strokeWidth={3} />
              </div>
              <div className="flex flex-col text-sm text-slate-700 leading-tight">
                <span className="font-semibold group-hover:text-slate-900 transition-colors break-words">
                  {notebook}
                </span>
                <span className="text-xs text-slate-400 mt-1">
                  Pinecone Source
                </span>
              </div>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}