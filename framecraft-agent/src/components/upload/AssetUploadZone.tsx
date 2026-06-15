import React, { useRef, useState } from 'react';
import { Upload, Plus } from 'lucide-react';
import { useStudioWorkflow } from '../../hooks/useStudioWorkflow';

export default function AssetUploadZone() {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { uploadFiles } = useStudioWorkflow();

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    await uploadFiles(files);
  };

  return (
    <div
      className={`relative rounded-lg border-2 border-dashed transition-all duration-300 ${
        isDragging
          ? 'border-primary bg-primary/10 scale-[1.02]'
          : 'border-white/15 bg-white/[0.02] hover:border-white/25'
      }`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        void handleFiles(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        accept="video/*,image/*,audio/*"
        onChange={(e) => void handleFiles(e.target.files)}
      />
      {isDragging && (
        <div className="absolute inset-0 rounded-lg bg-primary/10 flex items-center justify-center pointer-events-none z-10">
          <span className="text-primary-light font-semibold text-sm">松开上传素材</span>
        </div>
      )}

      <div className="flex flex-col items-center justify-center py-8 px-4 gap-3">
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-all ${
          isDragging ? 'bg-primary/20 scale-110' : 'bg-white/5'
        }`}>
          <Upload className={`w-5 h-5 ${isDragging ? 'text-primary-light' : 'text-text-muted'}`} />
        </div>
        <div className="text-center">
          <p className="text-sm text-text-secondary font-medium">
            拖拽视频、图片或音频到这里
          </p>
          <p className="text-xs text-text-muted mt-1">
            支持口播视频、B-roll、图片、BGM
          </p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="gradient-btn px-4 py-1.5 rounded-lg text-xs flex items-center gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          选择文件
        </button>
      </div>
    </div>
  );
}
