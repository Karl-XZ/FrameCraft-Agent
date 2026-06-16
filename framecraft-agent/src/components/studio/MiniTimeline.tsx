import React from 'react';
import { useProjectStore } from '../../store/projectStore';

const COLORS = ['bg-primary', 'bg-secondary', 'bg-accent', 'bg-warning', 'bg-success', 'bg-info'];

function formatSec(sec: number): string {
  if (!Number.isFinite(sec)) return '—';
  const s = Math.round(sec);
  return s >= 60 ? `${Math.floor(s / 60)}m${s % 60}s` : `${s}s`;
}

export default function MiniTimeline() {
  const editPlan = useProjectStore((s) => s.editPlan);

  const scenes = (editPlan?.scenes || []) as Array<{
    caption?: string;
    timeline_start?: number;
    timeline_end?: number;
  }>;

  if (!scenes.length) {
    return (
      <div className="glass-card rounded-xl p-4">
        <span className="text-xs text-text-muted">完成 Agent 分析后将显示剪辑方案时间线</span>
      </div>
    );
  }

  const total = editPlan?.target_duration
    || Math.max(...scenes.map((sc) => Number(sc.timeline_end) || 0), 1);

  return (
    <div className="glass-card rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-text-secondary">剪辑方案时间线</span>
        <span className="text-xs text-text-muted">总时长 {formatSec(total)}</span>
      </div>

      <div className="flex gap-1 h-8 rounded-lg overflow-hidden">
        {scenes.map((seg, i) => {
          const start = Number(seg.timeline_start) || 0;
          const end = Number(seg.timeline_end) || start + 1;
          const dur = Math.max(0.1, end - start);
          const widthPct = `${Math.max(4, (dur / total) * 100)}%`;
          const color = COLORS[i % COLORS.length];
          const label = seg.caption?.slice(0, 12) || `场景 ${i + 1}`;
          return (
            <div
              key={i}
              className={`${color} rounded flex items-center justify-center relative group cursor-default`}
              style={{ width: widthPct }}
              title={`${label}: ${formatSec(dur)}`}
            >
              <span className="text-[10px] font-semibold text-white/90 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap px-1">
                {label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="flex gap-1 mt-2 flex-wrap">
        {scenes.map((seg, i) => {
          const start = Number(seg.timeline_start) || 0;
          const end = Number(seg.timeline_end) || start + 1;
          const dur = Math.max(0.1, end - start);
          const widthPct = `${Math.max(8, (dur / total) * 100)}%`;
          const color = COLORS[i % COLORS.length];
          const label = seg.caption?.slice(0, 10) || `场景${i + 1}`;
          return (
            <div key={i} className="flex items-center gap-1 min-w-0" style={{ width: widthPct }}>
              <div className={`w-2 h-2 rounded-full shrink-0 ${color}`} />
              <span className="text-[10px] text-text-muted truncate">{label}</span>
              <span className="text-[10px] text-text-muted ml-auto shrink-0">{formatSec(dur)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
