import React, { useEffect } from 'react';
import { X, Shield, Monitor, Zap } from 'lucide-react';
import { useProjectStore } from '../../store/projectStore';
import { api } from '../../api/client';

const PROVIDERS = ['OpenAI', 'Anthropic', 'Google', 'DeepSeek', 'Qwen', 'OpenRouter', '本地模型', '其他'];
const RATIOS = ['9:16', '16:9', '1:1'];
const RESOLUTIONS = ['720p快速预览', '1080p正式导出', '4K旗舰版'];
const DRAFT_TARGETS = ['CapCut International', '剪映兼容草稿'];

export default function ModelSettingsDrawer() {
  const {
    showSettingsDrawer, setShowSettingsDrawer,
    modelProvider, setModelProvider,
    apiKey, setApiKey,
    videoRatio, setVideoRatio,
    videoResolution, setVideoResolution,
    frameRate, setFrameRate,
    targetDuration, setTargetDuration,
    draftTarget, setDraftTarget,
  } = useProjectStore();

  useEffect(() => {
    if (!showSettingsDrawer) return;
    void api.getSettings().then((s) => {
      if (s.provider) setModelProvider(s.provider);
      if (s.api_key) setApiKey(s.api_key);
    });
  }, [showSettingsDrawer, setApiKey, setModelProvider]);

  const save = async () => {
    await api.saveSettings({
      provider: modelProvider,
      api_key: apiKey,
      text_model: 'gpt-4o-mini',
      vision_model: 'gpt-4o-mini',
      asr_model: 'base',
      base_url: '',
    });
    setShowSettingsDrawer(false);
  };

  if (!showSettingsDrawer) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Scrim */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={() => setShowSettingsDrawer(false)}
      />

      {/* Drawer */}
      <div className="relative ml-auto w-[480px] h-full glass-strong border-l border-white/10 flex flex-col animate-slide-in-right overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/8">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/15 flex items-center justify-center">
              <Monitor className="w-4 h-4 text-primary-light" />
            </div>
            <span className="text-base font-bold text-text-main">模型设置</span>
          </div>
          <button
            onClick={() => setShowSettingsDrawer(false)}
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4 text-text-muted" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* Model Provider */}
          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main flex items-center gap-2">
              <Zap className="w-3.5 h-3.5 text-primary-light" />
              模型提供商
            </label>
            <div className="grid grid-cols-2 gap-2">
              {PROVIDERS.map((p) => (
                <button
                  key={p}
                  onClick={() => setModelProvider(p)}
                  className={`px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
                    modelProvider === p
                      ? 'bg-primary/15 text-primary-light border-primary/30'
                      : 'bg-white/4 text-text-secondary border-white/8 hover:border-white/15'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* API Key */}
          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-warning" />
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/8 text-sm text-text-main placeholder:text-text-muted focus:outline-none focus:border-primary/40 transition-all"
            />
            <div className="flex items-start gap-2 p-3 rounded-lg bg-warning/10 border border-warning/15">
              <Shield className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />
              <p className="text-xs text-warning/90 leading-relaxed">
                API Key 仅本地存储，不会传输到任何第三方服务器，请放心使用。
              </p>
            </div>
          </div>

          {/* Video Output */}
          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main">视频输出设置</label>

            <div className="space-y-3">
              {/* Ratio */}
              <div>
                <p className="text-xs text-text-muted mb-2">画面比例</p>
                <div className="flex gap-2">
                  {RATIOS.map((r) => (
                    <button
                      key={r}
                      onClick={() => setVideoRatio(r)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${
                        videoRatio === r
                          ? 'bg-primary/15 text-primary-light border-primary/30'
                          : 'bg-white/4 text-text-secondary border-white/8'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              {/* Resolution */}
              <div>
                <p className="text-xs text-text-muted mb-2">分辨率</p>
                <div className="flex gap-2">
                  {RESOLUTIONS.map((r) => (
                    <button
                      key={r}
                      onClick={() => setVideoResolution(r)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium border transition-all ${
                        videoResolution === r
                          ? 'bg-primary/15 text-primary-light border-primary/30'
                          : 'bg-white/4 text-text-secondary border-white/8'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>

              {/* Frame rate */}
              <div className="flex items-center justify-between">
                <p className="text-xs text-text-muted">帧率</p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setFrameRate(Math.max(24, frameRate - 1))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    -
                  </button>
                  <span className="text-sm font-mono text-text-main w-12 text-center">{frameRate} fps</span>
                  <button
                    onClick={() => setFrameRate(Math.min(60, frameRate + 1))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Duration */}
              <div className="flex items-center justify-between">
                <p className="text-xs text-text-muted">目标时长</p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setTargetDuration(Math.max(15, targetDuration - 5))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    -
                  </button>
                  <span className="text-sm font-mono text-text-main w-12 text-center">{targetDuration}s</span>
                  <button
                    onClick={() => setTargetDuration(Math.min(300, targetDuration + 5))}
                    className="w-7 h-7 rounded-lg bg-white/5 border border-white/8 text-xs text-text-secondary hover:bg-white/10"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Draft export */}
          <div className="space-y-3">
            <label className="text-sm font-semibold text-text-main">草稿导出目标</label>
            <div className="space-y-2">
              {DRAFT_TARGETS.map((t) => (
                <button
                  key={t}
                  onClick={() => setDraftTarget(t)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border transition-all text-left ${
                    draftTarget === t
                      ? 'bg-primary/10 border-primary/25 text-primary-light'
                      : 'bg-white/4 border-white/8 text-text-secondary hover:border-white/15'
                  }`}
                >
                  <div className={`w-3 h-3 rounded-full border-2 ${
                    draftTarget === t ? 'border-primary-light bg-primary-light' : 'border-white/20'
                  }`} />
                  <div>
                    <p className="text-sm font-medium">{t}</p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {t === 'CapCut International'
                        ? '导出为 CapCut 国际版可编辑的草稿格式'
                        : '导出为国内剪映（手机版/专业版）兼容草稿'}
                    </p>
                  </div>
                </button>
              ))}
            </div>
            <p className="text-xs text-text-muted p-3 rounded-lg bg-white/4 border border-white/6">
              剪映兼容草稿使用标准 XML 格式，可直接导入剪映专业版或手机版，无需额外转换。
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/8">
          <button type="button" onClick={() => void save()} className="gradient-btn w-full py-3 rounded-xl text-sm font-semibold">
            保存设置
          </button>
        </div>
      </div>
    </div>
  );
}
