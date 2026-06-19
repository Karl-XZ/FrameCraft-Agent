import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ChevronDown, FolderOpen, Loader2, Plus, RefreshCw } from 'lucide-react';
import { api, type BackendProject } from '../../api/client';
import { useProjectStore } from '../../store/projectStore';
import { useStudioWorkflow } from '../../hooks/useStudioWorkflow';

const STATUS_LABEL: Record<string, string> = {
  created: '已创建',
  uploading: '上传中',
  analyzing: '分析中',
  planning: '规划中',
  rendering: '渲染中',
  chatting: 'Agent 对话中',
  exporting_draft: '导出草稿',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

function formatTime(iso?: string) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function ProjectSelector() {
  const { projectId, clearProject } = useProjectStore();
  const { loadProject } = useStudioWorkflow();
  const navigate = useNavigate();
  const rootRef = useRef<HTMLDivElement>(null);

  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<BackendProject[]>([]);
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      setProjects(await api.listProjects());
    } catch {
      setProjects([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  useEffect(() => {
    if (!open) return;
    void fetchProjects();
    const onDocClick = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open, fetchProjects]);

  const current = projects.find((p) => p.id === projectId);

  const handleSelect = async (id: string) => {
    if (id === projectId) {
      setOpen(false);
      return;
    }
    setSwitching(true);
    try {
      await loadProject(id);
      navigate(`/studio?project=${id}`, { replace: true });
      setOpen(false);
    } finally {
      setSwitching(false);
    }
  };

  const handleNew = () => {
    clearProject();
    navigate('/studio', { replace: true });
    setOpen(false);
  };

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={switching}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg glass border border-white/10 text-xs text-text-secondary hover:text-text-main hover:border-primary/30 transition-all max-w-[220px]"
      >
        {switching ? (
          <Loader2 className="w-3.5 h-3.5 spinner flex-shrink-0" />
        ) : (
          <FolderOpen className="w-3.5 h-3.5 text-primary-light flex-shrink-0" />
        )}
        <span className="truncate font-medium text-text-main">
          {switching ? '切换项目中…' : current?.name || (projectId ? '当前项目' : '选择项目')}
        </span>
        <ChevronDown className={`w-3.5 h-3.5 flex-shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+8px)] z-50 w-[320px] glass-strong border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-fade-in-up">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/8">
            <div>
              <p className="text-sm font-semibold text-text-main">本地项目</p>
              <p className="text-[10px] text-text-muted mt-0.5">选择已有项目或新建</p>
            </div>
            <button
              type="button"
              onClick={() => void fetchProjects()}
              className="p-1.5 rounded-lg hover:bg-white/10 text-text-muted hover:text-text-main"
              title="刷新列表"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'spinner' : ''}`} />
            </button>
          </div>

          <div className="max-h-[320px] overflow-y-auto p-2 space-y-1">
            {loading && projects.length === 0 ? (
              <div className="flex items-center justify-center gap-2 py-8 text-xs text-text-muted">
                <Loader2 className="w-4 h-4 spinner" />
                加载项目…
              </div>
            ) : projects.length === 0 ? (
              <p className="text-xs text-text-muted text-center py-8">暂无本地项目</p>
            ) : (
              projects.map((p) => {
                const active = p.id === projectId;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => void handleSelect(p.id)}
                    className={`w-full text-left px-3 py-2.5 rounded-lg border transition-all ${
                      active
                        ? 'bg-primary/12 border-primary/30'
                        : 'bg-white/[0.03] border-transparent hover:bg-white/[0.06] hover:border-white/10'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-text-main truncate">{p.name}</p>
                        <p className="text-[10px] text-text-muted font-mono truncate mt-0.5">{p.id}</p>
                        <p className="text-[10px] text-text-muted mt-1">
                          {p.aspect_ratio} · {p.target_duration}s · {formatTime(p.updated_at)}
                        </p>
                      </div>
                      {active && <Check className="w-4 h-4 text-primary-light flex-shrink-0 mt-0.5" />}
                    </div>
                    <div className="flex items-center gap-1.5 mt-2">
                      <span className="px-2 py-0.5 rounded-full text-[10px] bg-white/5 border border-white/10 text-text-secondary">
                        {STATUS_LABEL[p.status] || p.status}
                      </span>
                      {p.current_version_id && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-secondary/10 border border-secondary/20 text-secondary">
                          已有成片
                        </span>
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="p-2 border-t border-white/8">
            <button
              type="button"
              onClick={handleNew}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-dashed border-white/15 text-xs text-text-secondary hover:text-primary-light hover:border-primary/30 hover:bg-primary/5 transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              新建空白项目
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
