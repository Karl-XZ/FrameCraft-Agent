import json
import time
import urllib.request
import uuid
import sys
from pathlib import Path

BASE = 'http://127.0.0.1:8002'
VIDEO = Path(r'E:\bilidown\【4k60帧】我爸得了mvp原视频.mp4')

def req(method, path, data=None, headers=None):
    url = BASE + path
    hdrs = headers or {}
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8')
            hdrs = {**hdrs, 'Content-Type': 'application/json'}
        elif isinstance(data, (bytes, bytearray)):
            body = data
    request = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(request, timeout=120) as resp:
        text = resp.read().decode('utf-8')
        return json.loads(text) if text else None

def wait_job(job_id, tag):
    print(f'[{tag}] job={job_id} polling...')
    while True:
        job = req('GET', f'/api/jobs/{job_id}')
        print(f"[{tag}] status={job.get('status')} progress={job.get('progress')} step={job.get('current_step')}")
        if job.get('status') in ('completed', 'failed', 'cancelled'):
            return job
        time.sleep(3)

project = req('POST', '/api/projects', {
    'name': 'E2E-' + uuid.uuid4().hex[:6],
    'aspect_ratio': '9:16',
    'target_duration': 60,
    'target_style': 'modern_talking_head',
    'output_language': 'zh',
    'generate_draft': True,
    'keep_hyperframes': True,
})
project_id = project['id']
print('PROJECT', project_id)

boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
filename = VIDEO.name.encode('utf-8', 'ignore').decode('latin1')
parts = []
parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="user_label"\r\n\r\n口播视频\r\n').encode('utf-8'))
parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="user_note"\r\n\r\n主素材，完整跑流程\r\n').encode('utf-8'))
parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: video/mp4\r\n\r\n').encode('latin1'))
parts.append(VIDEO.read_bytes())
parts.append(f'\r\n--{boundary}--\r\n'.encode('utf-8'))
body = b''.join(parts)
asset = req('POST', f'/api/projects/{project_id}/assets/upload', body, {
    'Content-Type': f'multipart/form-data; boundary={boundary}'
})
print('ASSET', asset['id'], asset['file_name'])

job_analyze = req('POST', f'/api/projects/{project_id}/assets/analyze', {'strategy': 'complete', 'platform': 'douyin'})
result_analyze = wait_job(job_analyze['id'], 'ANALYZE')
if result_analyze.get('status') != 'completed':
    print('ANALYZE_FAILED', result_analyze.get('error_message'))
    sys.exit(2)

job_generate = req('POST', f'/api/projects/{project_id}/generate', {'resolution': '1080p', 'fps': 30, 'strategy': 'complete'})
result_generate = wait_job(job_generate['id'], 'GENERATE')
if result_generate.get('status') != 'completed':
    print('GENERATE_FAILED', result_generate.get('error_message'))
    sys.exit(3)

chat = req('POST', f'/api/projects/{project_id}/chat', {
    'message': '把字幕改成更醒目的黄色大字，节奏稍快一点',
    'apply': True,
})
print('CHAT_STATUS', chat.get('status'), 'JOB', chat.get('job_id'))
if chat.get('job_id'):
    result_chat = wait_job(chat['job_id'], 'CHAT_REGEN')
    if result_chat.get('status') != 'completed':
        print('CHAT_REGEN_FAILED', result_chat.get('error_message'))
        sys.exit(4)

versions = req('GET', f'/api/projects/{project_id}/versions')
print('VERSIONS', len(versions))
if versions:
    latest = versions[0]
    print('LATEST_VERSION', latest['id'], latest['version_number'])
    print('FILES', json.dumps({k: latest.get(k) for k in [
        'preview_url', 'draft_url', 'timeline_url', 'hyperframes_url',
        'subtitles_url', 'cover_url', 'publish_copy_url'
    ]}, ensure_ascii=False))
    guide = req('GET', f"/api/projects/{project_id}/versions/{latest['id']}/import-guide")
    print('IMPORT_GUIDE', (guide.get('content') or '')[:120])

print('DONE PROJECT', project_id)

