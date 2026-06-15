import React from 'react';

const SEGMENTS = [
  { label: 'Hook', color: 'bg-primary', width: '12%', time: '7s' },
  { label: '口播第一段', color: 'bg-secondary', width: '25%', time: '15s' },
  { label: '产品B-roll', color: 'bg-accent', width: '20%', time: '12s' },
  { label: '图文动画', color: 'bg-warning', width: '18%', time: '10s' },
  { label: '总结CTA', color: 'bg-success', width: '25%', time: '14s' },
];

export default function MiniTimeline() {
  return (
    <div className="glass-card rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-semibold text-text-secondary">视频时间线</span>
        <span className="text-xs text-text-muted">总时长 58s</span>
      </div>

      {/* Timeline bar */}
      <div className="flex gap-1 h-8 rounded-lg overflow-hidden">
        {SEGMENTS.map((seg, i) => (
          <div
            key={i}
            className={`${seg.color} rounded flex items-center justify-center relative group cursor-pointer`}
            style={{ width: seg.width }}
            title={`${seg.label}: ${seg.time}`}
          >
            <span className="text-[10px] font-semibold text-white/90 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap px-1">
              {seg.label}
            </span>
          </div>
        ))}
      </div>

      {/* Labels */}
      <div className="flex gap-1 mt-2">
        {SEGMENTS.map((seg, i) => (
          <div key={i} className="flex items-center gap-1" style={{ width: seg.width }}>
            <div className={`w-2 h-2 rounded-full ${seg.color}`} />
            <span className="text-[10px] text-text-muted truncate">{seg.label}</span>
            <span className="text-[10px] text-text-muted ml-auto">{seg.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
