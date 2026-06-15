import { useCallback, useRef } from 'react';
import {
  api,
  formatDuration,
  formatSize,
  mapAssetType,
} from '../../api/client';
import { useProjectStore, type Asset } from '../../store/projectStore';

export function useStudioWorkflow() {
  const store = useProjectStore();
  const jobEsRef = useRef<EventSource | null>(null);

  const ensureProject = useCallback(async () => {
    if (store.projectId) return store.projectId;
    const p = await api.createProject({
      name: '帧造 Agent 项目',
      aspect_ratio: store.videoRatio,
      target_duration: store.targetDuration,
    });
    store.setProjectId(p.id);
    return p.id;
  }, [store]);

  const refreshAssets = useCallback(async (projectId: string) => {
    const list = await api.listAssets(projectId);
    const mapped: Asset[] = list.map((a) => ({
      id: a.id,
      filename: a.file_name,
      type: mapAssetType(a.user_label, a.file_type),
      duration: formatDuration(a.duration),
      size: formatSize(a.size),
      note: a.user_note,
      status: a.analysis_status === 'completed' ? '分析完成' : a.analysis_status === 'transcribed' ? '已转录' : '已上传',
      thumbnail: a.thumbnail_url ? api.fileUrl(a.thumbnail_url) : undefined,
    }));
    store.setAssets(mapped);
  }, [store]);

  const uploadFiles = useCallback(
    async (files: FileList | File[]) => {
      store.setError(null);
      const projectId = await ensureProject();
      for (const file of Array.from(files)) {
        const label =
          file.type.startsWith('video') && !store.assets.some((a) => a.type === '口播视频')
            ? '口播视频'
            : file.type.startsWith('audio')
              ? '音频'
              : file.type.startsWith('image')
                ? file.name.toLowerCase().includes('logo')
                  ? 'LOGO'
                  : '图片'
                : 'B-roll';
        await api.uploadAsset(projectId, file, label, '');
      }
      await refreshAssets(projectId);
    },
    [ensureProject, refreshAssets, store]
  );

  const watchJob = useCallback(
    (jobId: string, onDone?: () => void) => {
      jobEsRef.current?.close();
      jobEsRef.current = api.watchJob(jobId, (job) => {
        store.setTaskText(job.current_step || '处理中');
        if (job.type === 'analyze' || store.step === 'analyze') {
          store.setOverallProgress(Math.round(job.progress));
          store.setCurrentAnalyzeTask(job.current_step);
        }
        if (job.type === 'generate' || store.step === 'generate') {
          const p = Math.round(job.progress);
          store.setGenerateHyperFramesProgress(Math.min(100, p));
          store.setGenerateDraftProgress(Math.min(100, Math.max(0, p - 10)));
        }
        if (job.status === 'failed') {
          store.setError(job.error_message || '任务失败');
        }
        if (job.status === 'completed') {
          onDone?.();
        }
      });
    },
    [store]
  );

  const startAnalyze = useCallback(async () => {
    const projectId = await ensureProject();
    if (store.assets.length === 0) {
      store.setError('请先上传至少一个素材');
      return;
    }
    store.setStep('analyze');
    store.setOverallProgress(0);
    const job = await api.analyze(projectId);
    watchJob(job.id, async () => {
      const plan = await api.getEditPlan(projectId);
      store.setEditPlan(plan);
      store.setStep('plan');
      store.setTaskText('分析完成，请确认剪辑方案');
      await refreshAssets(projectId);
    });
  }, [ensureProject, refreshAssets, store, watchJob]);

  const startGenerate = useCallback(async () => {
    const projectId = store.projectId;
    if (!projectId) return;
    store.setStep('generate');
    store.setGenerateHyperFramesProgress(0);
    store.setGenerateDraftProgress(0);
    const job = await api.generate(projectId);
    watchJob(job.id, async () => {
      const versions = await api.listVersions(projectId);
      store.setVersions(versions);
      const latest = versions[0];
      if (latest) {
        store.setCurrentVersionId(latest.id);
        store.setVersion(`v${latest.version_number}.0`);
        if (latest.preview_url) store.setPreviewUrl(api.fileUrl(latest.preview_url));
      }
      store.setStep('result');
      store.setTaskText('生成完成');
    });
  }, [store, watchJob]);

  const sendChat = useCallback(
    async (message: string) => {
      const projectId = store.projectId;
      if (!projectId || !message.trim()) return;
      store.addChatMessage({ id: crypto.randomUUID(), role: 'user', text: message, timestamp: Date.now() });
      const res = await api.chat(projectId, message);
      store.addChatMessage({
        id: res.id,
        role: 'agent',
        text: res.content,
        timestamp: Date.now(),
        patch: res.patch,
      });
      if (res.patch) store.setPendingPatch(res.patch);
      if (res.job_id) {
        store.setStep('generate');
        store.setGenerateHyperFramesProgress(0);
        store.setGenerateDraftProgress(0);
        watchJob(res.job_id, async () => {
          const versions = await api.listVersions(projectId);
          store.setVersions(versions);
          const latest = versions[0];
          if (latest) {
            store.setCurrentVersionId(latest.id);
            store.setVersion(`v${latest.version_number}.0`);
            if (latest.preview_url) store.setPreviewUrl(api.fileUrl(latest.preview_url));
          }
          store.setStep('result');
          store.setTaskText('修改已应用并重新生成');
        });
      }
    },
    [store, watchJob]
  );

  return {
    ensureProject,
    uploadFiles,
    startAnalyze,
    startGenerate,
    sendChat,
    refreshAssets,
  };
}
