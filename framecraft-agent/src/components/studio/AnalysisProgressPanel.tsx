import React from 'react';
import { Check, Loader2, Circle } from 'lucide-react';
import GlassCard from '../ui/GlassCard';
import { useProjectStore } from '../../store/projectStore';

const TASK_LABELS = [
  '提取口播音频',
  'Whisper 转录',
  '分析口播结构',
  '抽帧理解 B-roll',
  '匹配素材备注',
  '生成剪辑方案',
];

export default function AnalysisProgressPanel() {
  const { overallProgress, currentAnalyzeTask } = useProjectStore();
  const activeIndex = Math.min(
    TASK_LABELS.length - 1,
    Math.floor((overallProgress / 100) * TASK_LABELS.length)
  );

  return (
    <div className="flex flex-col gap-5 h-full justify-center">
      <GlassCard className="relative overflow-hidden rounded-2xl p-8">
        <div className="relative z-10 flex flex-col items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-primary animate-dot-pulse" />
            <span className="text-lg font-bold text-text-main">正在理解你的素材</span>
          </div>
          <div className="relative w-36 h-36">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="44" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
              <circle
                cx="50" cy="50" r="44" fill="none"
                stroke="url(#progressGrad)" strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={`${overallProgress * 2.76} 276`}
                className="transition-all duration-700"
              />
              <defs>
                <linearGradient id="progressGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#7C3AED" />
                  <stop offset="50%" stopColor="#06B6D4" />
                  <stop offset="100%" stopColor="#F472B6" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-3xl font-extrabold gradient-text">{overallProgress}%</span>
            </div>
          </div>
          <p className="text-sm text-text-secondary">
            当前：<span className="text-primary-light font-medium">{currentAnalyzeTask}</span>
          </p>
        </div>
      </GlassCard>

      <div className="glass-card rounded-xl p-4 space-y-3">
        {TASK_LABELS.map((label, i) => {
          const status = i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending';
          return (
            <div key={label} className="flex items-center gap-3">
              {status === 'done' && <Check className="w-4 h-4 text-success flex-shrink-0" />}
              {status === 'active' && <Loader2 className="w-4 h-4 text-primary spinner flex-shrink-0" />}
              {status === 'pending' && <Circle className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />}
              <span className={`text-sm ${
                status === 'done' ? 'text-text-secondary line-through' :
                status === 'active' ? 'text-text-main font-medium' :
                'text-text-muted'
              }`}>
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
