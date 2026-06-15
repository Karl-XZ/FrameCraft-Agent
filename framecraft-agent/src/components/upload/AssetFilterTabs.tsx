import React, { useState } from 'react';
import { Upload, FileVideo, Image, Music, Hexagon, Folder } from 'lucide-react';
import { useProjectStore, AssetType } from '../../store/projectStore';

const FILTERS: { key: AssetType; label: string; icon: React.ReactNode }[] = [
  { key: 'all', label: '全部', icon: <Folder className="w-3 h-3" /> },
  { key: '口播视频', label: '口播视频', icon: <FileVideo className="w-3 h-3" /> },
  { key: 'B-roll', label: 'B-roll', icon: <Image className="w-3 h-3" /> },
  { key: '图片', label: '图片', icon: <Image className="w-3 h-3" /> },
  { key: '音频', label: '音频', icon: <Music className="w-3 h-3" /> },
  { key: 'LOGO', label: 'LOGO', icon: <Hexagon className="w-3 h-3" /> },
];

export default function AssetFilterTabs() {
  const { filter, setFilter } = useProjectStore();

  return (
    <div className="flex gap-1 flex-wrap">
      {FILTERS.map((f) => (
        <button
          key={f.key}
          onClick={() => setFilter(f.key)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
            filter === f.key
              ? 'bg-primary/20 text-primary-light border border-primary/30'
              : 'text-text-muted hover:text-text-secondary hover:bg-white/5 border border-transparent'
          }`}
        >
          {f.icon}
          {f.label}
        </button>
      ))}
    </div>
  );
}
