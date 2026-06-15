import React, { useState } from 'react';
import { X, FileVideo, Image, Music, Hexagon, Tag, MessageSquare, Star, Volume2, Crop, Brain } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';
import GradientButton from '../ui/GradientButton';

const TAGS = ['口播视频', 'B-roll', '图片', '音频', 'LOGO'];

export default function AssetDetailDrawer() {
  const { showAssetDrawer, setShowAssetDrawer, assets, selectedAssetId } = useProjectStore();
  const asset = assets.find((a) => a.id === selectedAssetId);
  const [note, setNote] = useState(asset?.note || '');
  const [mustUse, setMustUse] = useState(true);
  const [mute, setMute] = useState(false);
  const [allowCrop, setAllowCrop] = useState(true);
  const [priority, setPriority] = useState(7);

  if (!showAssetDrawer || !asset) return null;

  const TypeIcon = asset.type === '口播视频' || asset.type === 'B-roll' ? FileVideo :
    asset.type === '图片' ? Image :
    asset.type === '音频' ? Music : Hexagon;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Scrim */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setShowAssetDrawer(false)}
      />

      {/* Drawer */}
      <div className="relative ml-auto w-[420px] h-full glass-strong border-l border-white/10 flex flex-col animate-slide-in-right overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/8">
          <div className="flex items-center gap-2">
            <TypeIcon className="w-4 h-4 text-primary-light" />
            <span className="text-sm font-bold text-text-main">素材详情</span>
          </div>
          <button
            onClick={() => setShowAssetDrawer(false)}
            className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4 text-text-muted" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Filename */}
          <div>
            <p className="text-sm font-semibold text-text-main">{asset.filename}</p>
            <div className="flex items-center gap-3 mt-1">
              {asset.duration && <span className="text-xs text-text-muted">{asset.duration}</span>}
              <span className="text-xs text-text-muted">{asset.size}</span>
            </div>
          </div>

          {/* Tag */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5" />
              主标签
            </label>
            <div className="flex flex-wrap gap-2">
              {TAGS.map((t) => (
                <button
                  key={t}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    asset.type === t
                      ? 'bg-primary/15 text-primary-light border-primary/30'
                      : 'bg-white/4 text-text-secondary border-white/8 hover:border-white/15'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* User note */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <MessageSquare className="w-3.5 h-3.5" />
              素材备注
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="描述这段素材的使用意图..."
              className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary/40 transition-all resize-none h-24"
            />
          </div>

          {/* Toggles */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Star className="w-3.5 h-3.5 text-warning" />
                <span className="text-sm text-text-secondary">必须使用</span>
              </div>
              <button
                onClick={() => setMustUse(!mustUse)}
                className={`w-10 h-6 rounded-full transition-all relative ${
                  mustUse ? 'bg-primary' : 'bg-white/15'
                }`}
              >
                <div className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-all ${
                  mustUse ? 'left-5' : 'left-1'
                }`} />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Volume2 className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-sm text-text-secondary">静音</span>
              </div>
              <button
                onClick={() => setMute(!mute)}
                className={`w-10 h-6 rounded-full transition-all relative ${
                  mute ? 'bg-primary' : 'bg-white/15'
                }`}
              >
                <div className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-all ${
                  mute ? 'left-5' : 'left-1'
                }`} />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Crop className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-sm text-text-secondary">允许裁切</span>
              </div>
              <button
                onClick={() => setAllowCrop(!allowCrop)}
                className={`w-10 h-6 rounded-full transition-all relative ${
                  allowCrop ? 'bg-primary' : 'bg-white/15'
                }`}
              >
                <div className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-all ${
                  allowCrop ? 'left-5' : 'left-1'
                }`} />
              </button>
            </div>

            {/* Priority */}
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary flex items-center gap-2">
                <Star className="w-3.5 h-3.5 text-warning" />
                优先级
              </span>
              <div className="flex items-center gap-2">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                  <button
                    key={n}
                    onClick={() => setPriority(n)}
                    className={`w-5 h-5 rounded text-[9px] font-bold transition-all ${
                      n <= priority
                        ? 'bg-warning text-black'
                        : 'bg-white/8 text-text-muted hover:bg-white/15'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* AI Understanding */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-primary-light" />
              AI 理解结果
            </label>
            <div className="glass-card rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">内容标签</span>
                <span className="text-xs text-secondary">产品特写 · 户外场景</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">情绪色彩</span>
                <span className="text-xs text-warning">科技感 · 高级</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">推荐时段</span>
                <span className="text-xs text-primary-light">0:28 – 0:44</span>
              </div>
            </div>
          </div>

          {/* Keyframe preview */}
          {asset.type === '口播视频' || asset.type === 'B-roll' ? (
            <div className="space-y-2">
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                关键帧预览
              </label>
              <div className="flex gap-2">
                {['0s', '1/3', '1/2', '2/3', '1s'].map((t, i) => (
                  <div key={i} className="flex-1 aspect-video rounded-lg bg-black/40 border border-white/8 flex items-center justify-center">
                    <span className="text-[10px] text-text-muted">{t}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-white/8 flex gap-3">
          <button
            onClick={() => setShowAssetDrawer(false)}
            className="px-4 py-2.5 rounded-xl text-sm font-medium glass hover:bg-white/[0.08] transition-colors text-text-secondary border border-white/10 flex-1"
          >
            取消
          </button>
          <GradientButton size="md" className="flex-1 rounded-xl">
            保存
          </GradientButton>
        </div>
      </div>
    </div>
  );
}
