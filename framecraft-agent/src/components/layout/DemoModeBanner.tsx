import React from 'react';
import { AlertTriangle, ToggleRight } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';

export default function DemoModeBanner() {
  const { demoMode, setDemoMode } = useProjectStore();

  if (!demoMode) return null;

  return (
    <div className="bg-warning/15 border-b border-warning/30 px-6 py-2 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-4 h-4 text-warning" />
        <span className="text-sm text-warning font-medium">
          演示模式 · 当前使用预置素材，可快速展示完整流程
        </span>
      </div>
      <button
        onClick={() => setDemoMode(false)}
        className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-main transition-colors"
      >
        <span className="text-warning font-medium">快速演示模式</span>
        <ToggleRight className="w-5 h-5 text-warning" />
      </button>
    </div>
  );
}
