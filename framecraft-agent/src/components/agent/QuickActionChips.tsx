import React from 'react';
import { Zap } from 'lucide-react';

const ACTIONS = [
  '开头更有冲击力',
  '字幕改成黄色大字',
  '节奏加快',
  'BGM降低',
  '第二段换成产品界面素材',
];

interface QuickActionChipsProps {
  onSelect?: (text: string) => void;
}

export default function QuickActionChips({ onSelect }: QuickActionChipsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {ACTIONS.map((action) => (
        <button
          key={action}
          type="button"
          onClick={() => onSelect?.(action)}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-primary/15 border border-white/8 hover:border-primary/25 text-xs text-text-secondary hover:text-primary-light transition-all whitespace-nowrap"
        >
          <Zap className="w-3 h-3" />
          {action}
        </button>
      ))}
    </div>
  );
}
