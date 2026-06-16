import React from 'react';
import { Download } from 'lucide-react';
import Badge from '../ui/Badge';

interface DownloadResultCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  badge?: string;
  badgeVariant?: 'success' | 'primary' | 'info' | 'warning';
  size?: string;
}

export default function DownloadResultCard({
  title,
  description,
  icon,
  badge,
  badgeVariant = 'success',
  size,
}: DownloadResultCardProps) {
  return (
    <div className="glass-card rounded-xl p-4 flex flex-col gap-3 hover:border-primary/20 transition-all duration-200 cursor-pointer group">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-white/8 flex items-center justify-center group-hover:bg-primary/15 transition-colors">
            {icon}
          </div>
          <span className="text-sm font-semibold text-text-main">{title}</span>
        </div>
        {badge && <Badge variant={badgeVariant}>{badge}</Badge>}
      </div>
      <p className="text-xs text-text-muted">{description}</p>
      {size && <span className="text-xs text-text-muted">{size}</span>}
      <button className="flex items-center justify-center gap-2 py-2 rounded-lg bg-white/5 hover:bg-primary/15 border border-white/8 hover:border-primary/30 text-xs text-text-secondary hover:text-primary-light transition-all">
        <Download className="w-3.5 h-3.5" />
        下载
      </button>
    </div>
  );
}
