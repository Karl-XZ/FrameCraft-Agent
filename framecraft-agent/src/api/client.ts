const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return undefined as T;
}

export interface BackendProject {
  id: string;
  name: string;
  status: string;
  aspect_ratio: string;
  target_style: string;
  target_duration: number;
  output_language?: string;
  generate_draft?: boolean;
  keep_hyperframes?: boolean;
  current_version_id: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface BackendAsset {
  id: string;
  project_id: string;
  file_name: string;
  file_type: string;
  mime_type: string;
  size: number;
  duration: number | null;
  user_label: string;
  user_note: string;
  must_use: boolean;
  priority: number;
  analysis_status: string;
  thumbnail_url: string | null;
}

export interface BackendJob {
  id: string;
  project_id: string;
  type: string;
  status: string;
  progress: number;
  current_step: string;
  error_message: string | null;
  completed_steps?: string[];
  plan_substep?: string | null;
  plan_progress?: number;
  logs?: string[];
}

export interface EditPlan {
  video_concept: string;
  target_duration: number;
  style: string;
  hook: string;
  subtitle_style: string;
  bgm_note: string;
  scenes: Array<Record<string, unknown>>;
  broll_plan: Array<{ time: number; text: string; source: string; asset_id?: string }>;
}

export interface BackendVersion {
  id: string;
  version_number: number;
  preview_url: string | null;
  draft_url: string | null;
  subtitles_url: string | null;
  cover_url: string | null;
}

export interface CreateProjectBody {
  name: string;
  aspect_ratio?: string;
  target_duration?: number;
  target_style?: string;
  output_language?: string;
  generate_draft?: boolean;
  keep_hyperframes?: boolean;
}

export const api = {
  base: API_BASE,
  createProject: (body: CreateProjectBody) =>
    request<BackendProject>('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: body.name,
        aspect_ratio: body.aspect_ratio || '9:16',
        target_duration: body.target_duration || 60,
        target_style: body.target_style || 'modern_talking_head',
        output_language: body.output_language || 'zh',
        generate_draft: body.generate_draft ?? true,
        keep_hyperframes: body.keep_hyperframes ?? true,
      }),
    }),
  getProject: (projectId: string) => request<BackendProject>(`/api/projects/${projectId}`),
  deleteProject: (projectId: string) => request(`/api/projects/${projectId}`, { method: 'DELETE' }),
  listProjects: () => request<BackendProject[]>('/api/projects'),
  listAssets: (projectId: string) => request<BackendAsset[]>(`/api/projects/${projectId}/assets`),
  uploadAsset: async (projectId: string, file: File, user_label = '', user_note = '') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('user_label', user_label);
    fd.append('user_note', user_note);
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/assets/upload`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json() as Promise<BackendAsset>;
  },
  updateAsset: (assetId: string, body: Record<string, unknown>) =>
    request(`/api/assets/${assetId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  analyze: (projectId: string, opts?: { strategy?: string; platform?: string }) =>
    request<BackendJob>(`/api/projects/${projectId}/assets/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opts || {}),
    }),
  getEditPlan: (projectId: string) => request<EditPlan>(`/api/projects/${projectId}/edit-plan`),
  generate: (projectId: string, opts?: { resolution?: string; fps?: number; strategy?: string }) =>
    request<BackendJob>(`/api/projects/${projectId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opts || {}),
    }),
  applyPatch: (projectId: string, patch: Record<string, unknown>) =>
    request<BackendJob>(`/api/projects/${projectId}/apply-patch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patch }),
    }),
  cancelJob: (jobId: string) => request(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),
  getImportGuide: (projectId: string, versionId: string) =>
    request<{ content: string }>(`/api/projects/${projectId}/versions/${versionId}/import-guide`),
  getModelProviders: () => request<Record<string, unknown>>('/api/model-providers'),
  getJob: (jobId: string) => request<BackendJob>(`/api/jobs/${jobId}`),
  watchJob: (jobId: string, onEvent: (job: BackendJob) => void) => {
    const es = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`);
    es.onmessage = (ev) => {
      const data = JSON.parse(ev.data) as BackendJob;
      onEvent(data);
      if (['completed', 'failed', 'cancelled'].includes(data.status)) es.close();
    };
    return es;
  },
  listVersions: (projectId: string) => request<BackendVersion[]>(`/api/projects/${projectId}/versions`),
  chat: (projectId: string, message: string, apply = true) =>
    request<{ id: string; role: string; content: string; patch?: Record<string, unknown>; job_id?: string; status?: string }>(
      `/api/projects/${projectId}/chat`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message, apply }) }
    ),
  activateVersion: (projectId: string, versionId: string) =>
    request<{ ok: boolean; current_version_id: string }>(
      `/api/projects/${projectId}/versions/${versionId}/activate`,
      { method: 'POST' }
    ),
  getChat: (projectId: string) =>
    request<Array<{ id: string; role: string; content: string; created_at: string }>>(`/api/projects/${projectId}/chat`),
  getSettings: () => request<Record<string, string>>('/api/settings/model'),
  saveSettings: (body: Record<string, string>) =>
    request('/api/settings/model', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  fileUrl: (path: string) => `${API_BASE}${path}`,
};

export function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDuration(sec: number | null | undefined) {
  if (!sec) return undefined;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function mapAssetType(label: string, fileType: string): import('../store/projectStore').Asset['type'] {
  if (label.includes('口播') || label === '口播视频') return '口播视频';
  if (label.includes('B-roll') || label === 'B-roll') return 'B-roll';
  if (label.toUpperCase().includes('LOGO') || label === 'LOGO') return 'LOGO';
  if (fileType === 'audio' || label === '音频') return '音频';
  if (fileType === 'image') return '图片';
  if (fileType === 'video') return 'B-roll';
  return 'B-roll';
}
