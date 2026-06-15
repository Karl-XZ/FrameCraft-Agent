import React from 'react';
import { useProjectStore } from '../../store/projectStore';

export default function VideoPreviewArea() {
  const { previewUrl, version } = useProjectStore();

  if (!previewUrl) {
    return (
      <div className="relative rounded-2xl overflow-hidden bg-black/80 aspect-[9/16] flex items-center justify-center">
        <p className="text-xs text-text-muted">预览视频生成后将显示在这里</p>
      </div>
    );
  }

  return (
    <div className="relative rounded-2xl overflow-hidden bg-black aspect-[9/16] max-h-full">
      <video src={previewUrl} controls className="w-full h-full object-contain" />
      <div className="absolute top-3 right-3 px-2 py-1 rounded-md glass text-xs text-text-secondary">
        {version}
      </div>
    </div>
  );
}
