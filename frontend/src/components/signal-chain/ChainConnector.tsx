import React from 'react';
import { ArrowDown } from 'lucide-react';

interface Props {
  label: string;
  sub?: string;
}

export function ChainConnector({ label, sub }: Props) {
  return (
    <div className="flex flex-col items-center gap-1 py-2 select-none">
      <div className="w-px h-4 bg-gradient-to-b from-zinc-700 to-zinc-600" />
      <div className="flex items-center gap-3">
        <div className="h-px w-12 bg-zinc-800" />
        <div className="flex flex-col items-center gap-0.5">
          <ArrowDown className="w-3.5 h-3.5 text-zinc-600" />
          <span className="text-[9px] font-black text-zinc-600 uppercase tracking-[0.3em]">{label}</span>
          {sub && <span className="text-[8px] text-zinc-700 font-mono">{sub}</span>}
        </div>
        <div className="h-px w-12 bg-zinc-800" />
      </div>
      <div className="w-px h-4 bg-gradient-to-b from-zinc-600 to-zinc-700" />
    </div>
  );
}
