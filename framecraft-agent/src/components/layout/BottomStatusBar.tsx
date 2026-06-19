import React from 'react';
import { FileVideo, Zap } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';
import { api } from '../../api/client';

export default function BottomStatusBar() {
  const {
    taskText,
    overallProgress,
    version,
    generateHyperFramesProgress,
    generateDraftProgress,
    step,
    versions,
    currentVersionId,
  } = useProjectStore();
  const currentVersion = versions.find((v) => v.id === currentVersionId) || versions[0];

  const progress = step === 'generate'
    ? Math.round((generateHyperFramesProgress + generateDraftProgress) / 2)
    : step === 'analyze' ? overallProgress : step === 'result' ? 100 : 0;

  return (
    <div className="h-14 glass border-t border-white/8 flex items-center px-5 gap-5">
      {/* Left: Task info */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-2 h-2 rounded-full bg-secondary animate-pulse flex-shrink-0" />
        <span className="text-sm text-text-secondary truncate">{taskText}</span>
      </div>

      {/* Center: Progress bar */}
      <div className="flex-1 max-w-xs">
        <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-btn-gradient rounded-full transition-all duration-700 progress-shimmer"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-xs text-text-muted mt-0.5 block">{progress}%</span>
      </div>

      {/* Right: Version + downloads */}
      <div className="flex items-center gap-3 ml-auto">
        <span className="text-xs text-text-muted font-mono">{version}</span>

        <div className="flex items-center gap-1.5">
          <a
            href={currentVersion?.preview_url ? api.fileUrl(currentVersion.preview_url) : undefined}
            download
            aria-disabled={!currentVersion?.preview_url}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-white/8 text-xs transition-all ${
              currentVersion?.preview_url
                ? 'bg-white/5 hover:bg-white/10 text-text-secondary hover:text-text-main'
                : 'bg-white/[0.02] text-text-muted/50 pointer-events-none'
            }`}
          >
            <FileVideo className="w-3.5 h-3.5" />
            视频文件
          </a>
          <a
            href={currentVersion?.draft_url ? api.fileUrl(currentVersion.draft_url) : undefined}
            download
            aria-disabled={!currentVersion?.draft_url}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-white/8 text-xs transition-all ${
              currentVersion?.draft_url
                ? 'bg-white/5 hover:bg-white/10 text-text-secondary hover:text-text-main'
                : 'bg-white/[0.02] text-text-muted/50 pointer-events-none'
            }`}
          >
            <Zap className="w-3.5 h-3.5" />
            草稿文件
          </a>
        </div>
      </div>
    </div>
  );
}
