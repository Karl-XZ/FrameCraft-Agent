import React, { useEffect, useRef } from 'react';
import { Check, Loader2, Circle, Terminal } from 'lucide-react';
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

const PLAN_SUBSTEPS = [
  '整理场景分段',
  '匹配 B-roll 计划',
  '规划动效元素',
  '大模型润色文案',
  '保存剪辑方案',
];

function stepStatus(label: string, completed: string[], currentTask: string): 'done' | 'active' | 'pending' {
  if (completed.includes(label)) return 'done';
  const base = currentTask.split(' · ')[0];
  if (base === label || currentTask === label) return 'active';
  return 'pending';
}

export default function AnalysisProgressPanel() {
  const {
    overallProgress,
    currentAnalyzeTask,
    analyzeCompletedSteps,
    analyzeLogs,
    planProgress,
    planSubstep,
  } = useProjectStore();

  const terminalRef = useRef<HTMLPreElement>(null);
  const isPlanStep = currentAnalyzeTask.startsWith('生成剪辑方案');
  const displayTask = isPlanStep && planSubstep
    ? `生成剪辑方案 · ${planSubstep}`
    : currentAnalyzeTask;

  useEffect(() => {
    const el = terminalRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [analyzeLogs]);

  return (
    <div className="flex flex-col gap-5 h-full justify-center max-h-full overflow-y-auto py-2">
      <GlassCard className="relative overflow-hidden rounded-2xl p-8 flex-shrink-0">
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
          <p className="text-sm text-text-secondary text-center">
            当前：<span className="text-primary-light font-medium">{displayTask || '等待开始'}</span>
          </p>

          {isPlanStep && (
            <div className="w-full max-w-sm space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-muted">剪辑方案生成进度</span>
                <span className="text-primary-light font-mono">{planProgress}%</span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-btn-gradient rounded-full transition-all duration-500"
                  style={{ width: `${planProgress}%` }}
                />
              </div>
              <div className="flex flex-wrap gap-1.5 justify-center">
                {PLAN_SUBSTEPS.map((sub, idx) => {
                  const activeIdx = planSubstep ? PLAN_SUBSTEPS.indexOf(planSubstep) : (isPlanStep ? 0 : -1);
                  const done = planProgress >= 100 || (activeIdx >= 0 && idx < activeIdx);
                  const active = planSubstep === sub || (isPlanStep && !planSubstep && idx === 0);
                  return (
                    <span
                      key={sub}
                      className={`text-[10px] px-2 py-0.5 rounded-full border ${
                        active
                          ? 'border-primary/50 text-primary-light bg-primary/10'
                          : done
                            ? 'border-success/30 text-success/80 bg-success/5'
                            : 'border-white/10 text-text-muted'
                      }`}
                    >
                      {sub}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </GlassCard>

      <div className="glass-card rounded-xl p-4 space-y-3 flex-shrink-0">
        {TASK_LABELS.map((label) => {
          const status = stepStatus(label, analyzeCompletedSteps, currentAnalyzeTask);
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

      <div className="glass-card rounded-xl overflow-hidden flex flex-col min-h-[140px] max-h-[220px] flex-shrink-0">
        <div className="flex items-center gap-2 px-4 py-2 border-b border-white/8 bg-black/30">
          <Terminal className="w-3.5 h-3.5 text-secondary" />
          <span className="text-xs font-medium text-text-secondary">后台任务日志</span>
          <span className="text-[10px] text-text-muted ml-auto font-mono">live</span>
        </div>
        <pre
          ref={terminalRef}
          className="flex-1 overflow-y-auto p-3 text-[11px] leading-relaxed font-mono text-emerald-400/90 bg-[#0a0e17] whitespace-pre-wrap break-all"
        >
          {analyzeLogs.length > 0
            ? analyzeLogs.join('\n')
            : '> 等待后台输出…'}
        </pre>
      </div>
    </div>
  );
}
