import React, { useEffect, useState } from 'react';
import { X, FileVideo, Image, Music, Hexagon, Tag, MessageSquare, Star, Brain } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';
import { useStudioWorkflow } from '../../hooks/useStudioWorkflow';
import { api, type AssetAnalysis } from '../../api/client';
import GradientButton from '../ui/GradientButton';

const TAGS = ['口播视频', 'B-roll', '图片', '音频', 'LOGO'];

function formatBrollTime(sec: number | undefined): string {
  if (sec == null || Number.isNaN(sec)) return '—';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function AssetDetailDrawer() {
  const { showAssetDrawer, setShowAssetDrawer, assets, selectedAssetId } = useProjectStore();
  const { persistAsset } = useStudioWorkflow();
  const asset = assets.find((a) => a.id === selectedAssetId);
  const [note, setNote] = useState('');
  const [tag, setTag] = useState<string>('B-roll');
  const [mustUse, setMustUse] = useState(false);
  const [priority, setPriority] = useState(5);
  const [saving, setSaving] = useState(false);
  const [analysis, setAnalysis] = useState<AssetAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  useEffect(() => {
    if (!asset) return;
    setNote(asset.note || '');
    setTag(asset.type || 'B-roll');
    setMustUse(asset.mustUse);
    setPriority(asset.priority || 5);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [asset?.id]);

  useEffect(() => {
    if (!showAssetDrawer || !asset) {
      setAnalysis(null);
      return;
    }
    let cancelled = false;
    setAnalysisLoading(true);
    api
      .getAssetAnalysis(asset.id)
      .then((data) => {
        if (!cancelled) setAnalysis(data);
      })
      .catch(() => {
        if (!cancelled) setAnalysis({ ready: false, asset_id: asset.id });
      })
      .finally(() => {
        if (!cancelled) setAnalysisLoading(false);
      });
    return () => {
      cancelled = true;
    };
   
  }, [showAssetDrawer, asset?.id, asset]);

  if (!showAssetDrawer || !asset) return null;

  const onSave = async () => {
    setSaving(true);
    try {
      await persistAsset(asset.id, {
        user_label: tag,
        user_note: note,
        must_use: mustUse,
        priority,
      });
      setShowAssetDrawer(false);
    } finally {
      setSaving(false);
    }
  };

  const TypeIcon = asset.type === '口播视频' || asset.type === 'B-roll' ? FileVideo :
    asset.type === '图片' ? Image :
    asset.type === '音频' ? Music : Hexagon;

  const usageLabel = analysis?.ready && analysis.recommended_usage?.length
    ? analysis.recommended_usage.join(' · ')
    : null;
  const brollHint = analysis?.ready && analysis.broll_segments?.length
    ? analysis.broll_segments
        .map((b) => `${formatBrollTime(b.time)}${b.text ? ` · ${b.text}` : ''}`)
        .join('；')
    : null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setShowAssetDrawer(false)}
      />

      <div className="relative ml-auto w-[420px] h-full glass-strong border-l border-white/10 flex flex-col animate-slide-in-right overflow-y-auto">
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
          <div>
            <p className="text-sm font-semibold text-text-main">{asset.filename}</p>
            <div className="flex items-center gap-3 mt-1">
              {asset.duration && <span className="text-xs text-text-muted">{asset.duration}</span>}
              <span className="text-xs text-text-muted">{asset.size}</span>
              <span className="text-xs text-text-muted">{asset.status}</span>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <Tag className="w-3.5 h-3.5" />
              主标签
            </label>
            <div className="flex flex-wrap gap-2">
              {TAGS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTag(t)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    tag === t
                      ? 'bg-primary/15 text-primary-light border-primary/30'
                      : 'bg-white/4 text-text-secondary border-white/8 hover:border-white/15'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

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

          <div className="space-y-2">
            <label className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-primary-light" />
              AI 理解结果
            </label>
            <div className="glass-card rounded-lg p-3 space-y-2">
              {analysisLoading ? (
                <p className="text-xs text-text-muted">加载分析结果…</p>
              ) : !analysis?.ready ? (
                <p className="text-xs text-text-muted">尚未完成 Agent 分析，请先运行「分析素材」。</p>
              ) : (
                <>
                  {analysis.vision_status && analysis.vision_status !== 'vlm' ? (
                    <p className="text-xs text-warning border border-warning/20 rounded px-2 py-1">
                      视觉理解已降级（{analysis.vision_status}）{analysis.vision_error ? `：${analysis.vision_error}` : ''}
                    </p>
                  ) : null}
                  <div className="space-y-1">
                    <span className="text-xs text-text-muted">内容摘要</span>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      {analysis.auto_summary || '（无摘要）'}
                    </p>
                  </div>
                  {usageLabel ? (
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-text-muted shrink-0">推荐用途</span>
                      <span className="text-xs text-secondary text-right">{usageLabel}</span>
                    </div>
                  ) : null}
                  {analysis.ocr_text ? (
                    <div className="space-y-1">
                      <span className="text-xs text-text-muted">画面文字</span>
                      <p className="text-xs text-text-secondary">{analysis.ocr_text}</p>
                    </div>
                  ) : null}
                  {brollHint ? (
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs text-text-muted shrink-0">剪辑方案引用</span>
                      <span className="text-xs text-primary-light text-right">{brollHint}</span>
                    </div>
                  ) : null}
                </>
              )}
            </div>
          </div>

          {analysis?.ready && analysis.frame_urls && analysis.frame_urls.length > 0 ? (
            <div className="space-y-2">
              <label className="text-xs font-semibold text-text-muted uppercase tracking-wider">
                关键帧预览
              </label>
              <div className="flex gap-2 overflow-x-auto">
                {analysis.frame_urls.map((url) => (
                  <img
                    key={url}
                    src={api.fileUrl(url)}
                    alt=""
                    className="flex-shrink-0 w-20 aspect-video rounded-lg object-cover border border-white/8 bg-black/40"
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="px-5 py-4 border-t border-white/8 flex gap-3">
          <button
            onClick={() => setShowAssetDrawer(false)}
            className="px-4 py-2.5 rounded-xl text-sm font-medium glass hover:bg-white/[0.08] transition-colors text-text-secondary border border-white/10 flex-1"
          >
            取消
          </button>
          <GradientButton size="md" className="flex-1 rounded-xl" onClick={onSave} disabled={saving}>
            {saving ? '保存中…' : '保存'}
          </GradientButton>
        </div>
      </div>
    </div>
  );
}
