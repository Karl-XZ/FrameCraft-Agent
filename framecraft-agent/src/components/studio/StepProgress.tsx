import React from 'react';
import { Check, Loader2, AlertCircle, Circle } from 'lucide-react';
import { useProjectStore, Step } from '../../store/projectStore';

const STEPS: { key: Step; label: string }[] = [
  { key: 'upload', label: '上传素材' },
  { key: 'analyze', label: 'AI 分析' },
  { key: 'plan', label: '剪辑方案' },
  { key: 'generate', label: '生成视频' },
  { key: 'result', label: '导出修改' },
];

export default function StepProgress() {
  const { step } = useProjectStore();
  const activeIdx = STEPS.findIndex((s) => s.key === step);

  const getStatus = (idx: number) => {
    if (idx < activeIdx) return 'completed';
    if (idx === activeIdx) return 'active';
    return 'pending';
  };

  return (
    <div className="flex items-center gap-1">
      {STEPS.map((s, idx) => {
        const status = getStatus(idx);
        return (
          <React.Fragment key={s.key}>
            <div className="flex flex-col items-center gap-1">
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300
                  ${status === 'completed' ? 'bg-success/20 border-2 border-success text-success' : ''}
                  ${status === 'active' ? 'bg-primary/20 border-2 border-primary animate-pulse-glow' : ''}
                  ${status === 'pending' ? 'bg-white/5 border-2 border-white/15 text-text-muted' : ''}
    
                `}
              >
                {status === 'completed' && <Check className="w-4 h-4" />}
                {status === 'active' && <Loader2 className="w-4 h-4 spinner" />}
                {status === 'pending' && <Circle className="w-3.5 h-3.5" />}
              </div>
              <span className={`text-xs whitespace-nowrap ${
                status === 'active' ? 'text-primary-light font-semibold' :
                status === 'completed' ? 'text-success' :
                'text-text-muted'
              }`}>
                {s.label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`w-8 h-0.5 rounded-full mb-4 transition-all duration-500 ${
                idx < activeIdx ? 'bg-success' : idx === activeIdx ? 'bg-primary/50' : 'bg-white/10'
              }`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
