import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Zap, ArrowLeft, Sparkles } from 'lucide-react';
import { api } from '../api/client';

const RATIOS = [
  { v: '9:16', label: '9:16 竖屏' },
  { v: '16:9', label: '16:9 横屏' },
  { v: '1:1', label: '1:1 方形' },
];

const STYLES = [
  { v: 'modern_talking_head', label: '高级口播' },
  { v: 'product_demo', label: '产品介绍' },
  { v: 'educational_explainer', label: '知识科普' },
  { v: 'viral_short', label: '比赛路演' },
  { v: 'vlog', label: 'Vlog 解说' },
];

const LANGS = [
  { v: 'zh', label: '中文' },
  { v: 'en', label: '英文' },
  { v: 'bilingual', label: '双语' },
];

export default function NewProjectPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('未命名项目');
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [targetStyle, setTargetStyle] = useState('modern_talking_head');
  const [targetDuration, setTargetDuration] = useState(60);
  const [outputLanguage, setOutputLanguage] = useState('zh');
  const [generateDraft, setGenerateDraft] = useState(true);
  const [keepHyperframes, setKeepHyperframes] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      const p = await api.createProject({
        name: name.trim() || '未命名项目',
        aspect_ratio: aspectRatio,
        target_style: targetStyle,
        target_duration: targetDuration,
        output_language: outputLanguage,
        generate_draft: generateDraft,
        keep_hyperframes: keepHyperframes,
      });
      navigate(`/studio?project=${p.id}`);
    } finally {
      setSubmitting(false);
    }
  };

  const fieldCls = 'w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm text-text-main focus:outline-none focus:border-primary/40';

  return (
    <div className="min-h-screen bg-bg-main relative overflow-x-hidden">
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-[600px] h-[600px] rounded-full animate-orb-1"
          style={{ background: 'radial-gradient(circle, rgba(124,58,237,0.28), transparent 30%)' }} />
      </div>

      <nav className="relative z-10 flex items-center justify-between px-8 py-5">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-btn-gradient flex items-center justify-center shadow-glow">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-2xl font-extrabold tracking-tight">
            <span className="gradient-text">帧造</span>
            <span className="text-text-main"> Agent</span>
          </span>
        </Link>
        <Link to="/projects" className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-main transition-colors">
          <ArrowLeft className="w-4 h-4" /> 项目列表
        </Link>
      </nav>

      <main className="relative z-10 max-w-screen-sm mx-auto w-full px-8 py-6">
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-xs text-primary-light font-medium mb-3">
            <Sparkles className="w-3.5 h-3.5" /> 新建项目
          </div>
          <h1 className="text-3xl font-extrabold text-text-main">创建一个新项目</h1>
          <p className="text-sm text-text-muted mt-1">配置基础信息后即可上传素材并开始生成</p>
        </div>

        <div className="glass-card rounded-2xl p-6 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-text-secondary mb-1.5">项目名称</label>
            <input className={fieldCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：AI 剪辑产品介绍" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">视频比例</label>
              <select className={fieldCls} value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)}>
                {RATIOS.map((r) => <option key={r.v} value={r.v}>{r.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">目标时长（秒）</label>
              <input type="number" min={15} max={180} className={fieldCls} value={targetDuration}
                onChange={(e) => setTargetDuration(Number(e.target.value) || 60)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">视频风格</label>
              <select className={fieldCls} value={targetStyle} onChange={(e) => setTargetStyle(e.target.value)}>
                {STYLES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">输出语言</label>
              <select className={fieldCls} value={outputLanguage} onChange={(e) => setOutputLanguage(e.target.value)}>
                {LANGS.map((l) => <option key={l.v} value={l.v}>{l.label}</option>)}
              </select>
            </div>
          </div>

          <label className="flex items-center justify-between py-2 cursor-pointer">
            <span className="text-sm text-text-secondary">生成剪映 / CapCut 草稿</span>
            <input type="checkbox" checked={generateDraft} onChange={(e) => setGenerateDraft(e.target.checked)}
              className="w-4 h-4 accent-primary" />
          </label>
          <label className="flex items-center justify-between py-2 cursor-pointer">
            <span className="text-sm text-text-secondary">保留 HyperFrames 源工程</span>
            <input type="checkbox" checked={keepHyperframes} onChange={(e) => setKeepHyperframes(e.target.checked)}
              className="w-4 h-4 accent-primary" />
          </label>

          <button
            type="button"
            disabled={submitting}
            onClick={() => void handleCreate()}
            className="gradient-btn w-full px-5 py-3 rounded-xl text-sm font-bold flex items-center justify-center gap-2 shadow-glow disabled:opacity-60"
          >
            <Zap className="w-4 h-4" /> {submitting ? '创建中…' : '创建并进入工作台'}
          </button>
        </div>
      </main>
    </div>
  );
}
