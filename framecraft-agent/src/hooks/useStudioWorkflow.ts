import { useCallback, useRef } from 'react';
import {
  api,
  formatDuration,
  formatSize,
  mapAssetType,
} from '../api/client';
import { useProjectStore, type Asset } from '../store/projectStore';

export function useStudioWorkflow() {
  const store = useProjectStore();
  const jobEsRef = useRef<EventSource | null>(null);

  const ensureProject = useCallback(async () => {
    if (store.projectId) return store.projectId;
    const p = await api.createProject({
      name: '帧造 Agent 项目',
      aspect_ratio: store.videoRatio,
      target_duration: store.targetDuration,
      target_style: store.targetStyle,
      output_language: store.outputLanguage,
      generate_draft: store.generateDraft,
      keep_hyperframes: store.keepHyperframes,
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

  const loadProject = useCallback(async (projectId: string) => {
    store.setError(null);
    const p = await api.getProject(projectId);
    store.setProjectId(p.id);
    store.setVideoRatio(p.aspect_ratio);
    store.setTargetDuration(p.target_duration);
    store.setTargetStyle(p.target_style);
    if (p.output_language) store.setOutputLanguage(p.output_language);
    if (typeof p.generate_draft === 'boolean') store.setGenerateDraft(p.generate_draft);
    if (typeof p.keep_hyperframes === 'boolean') store.setKeepHyperframes(p.keep_hyperframes);
    await refreshAssets(projectId);
    const versions = await api.listVersions(projectId);
    store.setVersions(versions);
    if (versions.length && p.current_version_id) {
      const cur = versions.find((v) => v.id === p.current_version_id) || versions[0];
      store.setCurrentVersionId(cur.id);
      store.setVersion(`v${cur.version_number}.0`);
      if (cur.preview_url) store.setPreviewUrl(api.fileUrl(cur.preview_url));
      store.setStep('result');
      store.setTaskText('生成完成');
    } else {
      store.setCurrentVersionId(null);
      store.setPreviewUrl(null);
      store.setPendingPatch(null);
      store.setVersion('v1.0');
      store.setGenerateHyperFramesProgress(0);
      store.setGenerateDraftProgress(0);
      try {
        const plan = await api.getEditPlan(projectId);
        store.setEditPlan(plan);
        store.setStep('plan');
        store.setTaskText('分析完成，请确认剪辑方案');
      } catch {
        store.setEditPlan(null);
        store.setStep('upload');
        store.setTaskText('准备就绪');
      }
    }
    try {
      const history = await api.getChat(projectId);
      store.setChatMessages(
        history.map((m) => ({
          id: m.id,
          role: m.role as 'user' | 'agent',
          text: m.content,
          timestamp: Date.parse(m.created_at) || Date.now(),
        }))
      );
    } catch {
      /* ignore */
    }
  }, [refreshAssets, store]);

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
          store.setCurrentAnalyzeTask(job.current_step || '处理中');
          if (job.completed_steps) store.setAnalyzeCompletedSteps(job.completed_steps);
          if (job.logs) store.setAnalyzeLogs(job.logs);
          if (typeof job.plan_progress === 'number') store.setPlanProgress(job.plan_progress);
          store.setPlanSubstep(job.plan_substep ?? null);
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
    store.setAnalyzeCompletedSteps([]);
    store.setAnalyzeLogs([]);
    store.setPlanProgress(0);
    store.setPlanSubstep(null);
    const job = await api.analyze(projectId);
    watchJob(job.id, async () => {
      const plan = await api.getEditPlan(projectId);
      store.setEditPlan(plan);
      store.setStep('plan');
      store.setTaskText('分析完成，请确认剪辑方案');
      await refreshAssets(projectId);
    });
  }, [ensureProject, refreshAssets, store, watchJob]);

  const persistAsset = useCallback(async (assetId: string, body: Record<string, unknown>) => {
    await api.updateAsset(assetId, body);
    if (store.projectId) await refreshAssets(store.projectId);
  }, [refreshAssets, store]);

  const startGenerate = useCallback(async () => {
    const projectId = store.projectId;
    if (!projectId) return;
    store.setStep('generate');
    store.setGenerateHyperFramesProgress(0);
    store.setGenerateDraftProgress(0);
    const resolution = store.videoResolution.startsWith('720')
      ? '720p'
      : store.videoResolution.startsWith('4K')
        ? '4K旗舰版'
        : '1080p';
    const job = await api.generate(projectId, { resolution, fps: store.frameRate });
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

  const afterRegenerate = useCallback(
    (projectId: string, doneText: string) => async () => {
      const versions = await api.listVersions(projectId);
      store.setVersions(versions);
      const latest = versions[0];
      if (latest) {
        store.setCurrentVersionId(latest.id);
        store.setVersion(`v${latest.version_number}.0`);
        if (latest.preview_url) store.setPreviewUrl(api.fileUrl(latest.preview_url));
      }
      store.setStep('result');
      store.setTaskText(doneText);
    },
    [store]
  );

  // 发送修改：先生成方案，等待用户接受/撤销（需求 §11.3.6）
  const sendChat = useCallback(
    async (message: string) => {
      const projectId = store.projectId;
      if (!projectId || !message.trim()) return;
      store.addChatMessage({ id: crypto.randomUUID(), role: 'user', text: message, timestamp: Date.now() });
      try {
        const res = await api.chat(projectId, message, false);
        store.addChatMessage({
          id: res.id,
          role: 'agent',
          text: res.content,
          timestamp: Date.now(),
          patch: res.patch,
        });
        if (res.status === 'proposed' && res.patch) {
          store.setPendingPatch(res.patch);
        } else {
          store.setPendingPatch(null);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : '未知错误';
        store.addChatMessage({
          id: crypto.randomUUID(),
          role: 'agent',
          text: `对话请求失败：${msg}\n\n请确认后端 http://127.0.0.1:8000 已启动，并在「平台设置 → 模型配置」中保存 API Key。`,
          timestamp: Date.now(),
        });
      }
    },
    [store]
  );

  // 接受修改方案：应用 patch 并重新生成
  const acceptPatch = useCallback(async () => {
    const projectId = store.projectId;
    const patch = store.pendingPatch;
    if (!projectId || !patch) return;
    store.setPendingPatch(null);
    store.setStep('generate');
    store.setGenerateHyperFramesProgress(0);
    store.setGenerateDraftProgress(0);
    const job = await api.applyPatch(projectId, patch);
    store.addChatMessage({ id: crypto.randomUUID(), role: 'agent', text: '已接受修改，正在重新生成预览与剪映草稿…', timestamp: Date.now() });
    watchJob(job.id, afterRegenerate(projectId, '修改已应用并重新生成'));
  }, [afterRegenerate, store, watchJob]);

  // 撤销/放弃当前修改方案
  const discardPatch = useCallback(() => {
    store.setPendingPatch(null);
    store.addChatMessage({ id: crypto.randomUUID(), role: 'agent', text: '已撤销该修改方案，未做任何改动。', timestamp: Date.now() });
  }, [store]);

  // 回退到上一个版本（撤销已应用的修改）
  const revertToPreviousVersion = useCallback(async () => {
    const projectId = store.projectId;
    const versions = store.versions;
    if (!projectId || versions.length < 2) return;
    const currentIdx = versions.findIndex((v) => v.id === store.currentVersionId);
    const target = versions[currentIdx + 1] || versions[1];
    if (!target) return;
    await api.activateVersion(projectId, target.id);
    store.setCurrentVersionId(target.id);
    store.setVersion(`v${target.version_number}.0`);
    if (target.preview_url) store.setPreviewUrl(api.fileUrl(target.preview_url));
    store.addChatMessage({ id: crypto.randomUUID(), role: 'agent', text: `已撤销到上一版本 v${target.version_number}.0。`, timestamp: Date.now() });
  }, [store]);

  return {
    ensureProject,
    loadProject,
    uploadFiles,
    startAnalyze,
    startGenerate,
    sendChat,
    acceptPatch,
    discardPatch,
    revertToPreviousVersion,
    refreshAssets,
    persistAsset,
  };
}
