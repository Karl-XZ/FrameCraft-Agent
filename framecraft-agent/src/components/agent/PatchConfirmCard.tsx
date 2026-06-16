import React from 'react';
import { CheckCircle2, Check, X } from 'lucide-react';

interface PatchConfirmCardProps {
  patch: Record<string, unknown>;
  onAccept?: () => void;
  onDiscard?: () => void;
}

export default function PatchConfirmCard({ patch, onAccept, onDiscard }: PatchConfirmCardProps) {
  const ops = (patch.operations as Array<Record<string, unknown>>) || [];

  return (
    <div className="glass-card rounded-2xl p-4 space-y-3 animate-fade-in-up">
      <div className="flex items-center gap-2 mb-2">
        <CheckCircle2 className="w-4 h-4 text-primary-light" />
        <span className="text-sm font-bold text-text-main">AI 修改方案</span>
      </div>
      <p className="text-xs text-text-muted">{String(patch.description || '')}</p>
      <div className="space-y-2.5">
        {ops.map((op, i) => (
          <div key={i} className="flex items-start gap-2.5">
            <span className="w-5 h-5 rounded-full bg-primary/20 text-primary-light text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
              {i + 1}
            </span>
            <p className="text-xs text-text-secondary leading-relaxed">
              {String(op.op)} {op.target_id ? `→ ${String(op.target_id)}` : ''}
            </p>
          </div>
        ))}
        {!ops.length && <p className="text-xs text-text-muted">将重新生成预览与剪映草稿</p>}
      </div>
      {(onAccept || onDiscard) && (
        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={onAccept}
            className="gradient-btn flex-1 px-3 py-2 rounded-lg flex items-center justify-center gap-1.5 text-xs font-bold"
          >
            <Check className="w-3.5 h-3.5" />
            接受修改
          </button>
          <button
            type="button"
            onClick={onDiscard}
            className="px-3 py-2 rounded-lg flex items-center justify-center gap-1.5 text-xs font-semibold bg-white/5 border border-white/10 text-text-secondary hover:text-text-main hover:bg-white/[0.08] transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            撤销
          </button>
        </div>
      )}
    </div>
  );
}
