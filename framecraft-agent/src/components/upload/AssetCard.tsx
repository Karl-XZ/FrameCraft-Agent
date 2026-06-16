import React from 'react';
import { FileVideo, Image, Music, Hexagon } from 'lucide-react';
import Badge from '../ui/Badge';
import { Asset } from '../../store/projectStore';

const TYPE_ICONS: Record<string, React.ReactNode> = {
  '口播视频': <FileVideo className="w-4 h-4" />,
  'B-roll': <FileVideo className="w-4 h-4" />,
  '图片': <Image className="w-4 h-4" />,
  '音频': <Music className="w-4 h-4" />,
  'LOGO': <Hexagon className="w-4 h-4" />,
};

const TYPE_COLORS: Record<string, string> = {
  '口播视频': 'bg-primary/15 text-primary-light border-primary/25',
  'B-roll': 'bg-secondary/15 text-secondary border-secondary/25',
  '图片': 'bg-accent/15 text-accent border-accent/25',
  '音频': 'bg-warning/15 text-warning border-warning/25',
  'LOGO': 'bg-success/15 text-success border-success/25',
};

interface AssetCardProps {
  asset: Asset;
  onClick?: () => void;
}

export default function AssetCard({ asset, onClick }: AssetCardProps) {
  const statusVariant = asset.status === '已转录' ? 'success' : asset.status === '待分析' ? 'warning' : 'default';

  return (
    <div
      onClick={onClick}
      className="glass-card rounded-lg p-3 hover:border-primary/20 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 group"
    >
      {/* Thumbnail */}
      <div className="flex gap-3 items-start">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${TYPE_COLORS[asset.type] || 'bg-white/5'}`}>
          {TYPE_ICONS[asset.type]}
        </div>
        <div className="flex-1 min-w-0">
          {/* Filename */}
          <p className="text-sm font-medium text-text-main truncate group-hover:text-white transition-colors">
            {asset.filename}
          </p>
          {/* Meta */}
          <div className="flex items-center gap-2 mt-1">
            {asset.duration && (
              <span className="text-xs text-text-muted">{asset.duration}</span>
            )}
            <span className="text-xs text-text-muted">{asset.size}</span>
          </div>
          {/* Tag */}
          <div className="flex items-center gap-2 mt-2">
            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[asset.type] || 'bg-white/5 text-text-secondary'}`}>
              {asset.type}
            </span>
            <Badge variant={statusVariant}>{asset.status}</Badge>
          </div>
          {/* Note preview */}
          {asset.note && (
            <p className="text-xs text-text-muted mt-2 truncate">{asset.note}</p>
          )}
        </div>
      </div>
    </div>
  );
}
