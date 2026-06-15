import React from 'react';
import { FileVideo, CheckCircle2, Loader2, Eye } from 'lucide-react';
import GlassCard from '../ui/GlassCard';

export default function DemoPreviewCard() {
  return (
    <GlassCard className="p-5 flex flex-col gap-4 animate-float">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">工作台预览</span>
        <div className="flex items-center gap-1">
          <Eye className="w-3 h-3 text-info" />
          <span className="text-xs text-info">预览模式</span>
        </div>
      </div>

      {/* Video preview */}
      <div className="relative rounded-lg overflow-hidden bg-black/50 aspect-video flex items-center justify-center">
        <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center cursor-pointer hover:bg-white/20 transition-colors">
          <div className="w-0 h-0 border-l-[14px] border-l-white border-y-[8px] border-y-transparent ml-1" />
        </div>
        <div className="absolute bottom-2 left-2 right-2">
          <div className="h-1 bg-white/20 rounded-full">
            <div className="h-full w-2/5 bg-primary rounded-full" />
          </div>
        </div>
      </div>

      {/* Progress items */}
      <div className="space-y-2">
        {[
          { label: '提取口播音频', done: true },
          { label: 'Whisper 转录', done: true },
          { label: 'AI 分析结构', done: false },
          { label: '匹配 B-roll', done: false },
        ].map((item, i) => (
          <div key={i} className="flex items-center gap-2.5">
            {item.done ? (
              <CheckCircle2 className="w-4 h-4 text-success flex-shrink-0" />
            ) : (
              <Loader2 className="w-4 h-4 text-primary spinner flex-shrink-0" />
            )}
            <span className={`text-xs ${item.done ? 'text-text-secondary' : 'text-text-muted'}`}>
              {item.label}
            </span>
          </div>
        ))}
      </div>

      {/* File list */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 border border-primary/15">
          <FileVideo className="w-3.5 h-3.5 text-primary-light" />
          <span className="text-xs text-text-secondary truncate">产品口播_v2.mp4</span>
          <span className="text-xs text-primary-light ml-auto">3:24</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/5">
          <FileVideo className="w-3.5 h-3.5 text-secondary" />
          <span className="text-xs text-text-secondary truncate">产品细节展示.mp4</span>
          <span className="text-xs text-text-muted ml-auto">0:45</span>
        </div>
      </div>
    </GlassCard>
  );
}
