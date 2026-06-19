import React from 'react';
import { LayoutTemplate } from 'lucide-react';
import GlassCard from '../ui/GlassCard';

/** 落地页静态布局示意，不含虚假任务进度或文件名。 */
export default function DemoPreviewCard() {
  return (
    <GlassCard className="p-5 flex flex-col gap-4 animate-float">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted">工作台布局示意</span>
        <div className="flex items-center gap-1">
          <LayoutTemplate className="w-3 h-3 text-info" />
          <span className="text-xs text-info">非真实数据</span>
        </div>
      </div>

      <div className="relative rounded-lg overflow-hidden bg-black/50 aspect-video flex items-center justify-center border border-dashed border-white/10">
        <p className="text-xs text-text-muted px-4 text-center">
          上传素材并由 Codex Agent 分析后，此处显示 HyperFrames 预览成片
        </p>
      </div>

      <div className="space-y-2 text-xs text-text-muted">
        <p>· Agent 分析素材并生成剪辑方案</p>
        <p>· HyperFrames 渲染高级口播预览</p>
        <p>· 同步导出可编辑剪映草稿</p>
      </div>
    </GlassCard>
  );
}
