import json
import time
import urllib.request
import sys

BASE = 'http://127.0.0.1:8004'
PROJECT_ID = 'proj_22f471a0c8cb'

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
    with urllib.request.urlopen(request, timeout=300) as resp:
        text = resp.read().decode('utf-8')
        return json.loads(text) if text else None

def wait_job(job_id, tag):
    print(f'[{tag}] job={job_id} polling...', flush=True)
    while True:
        job = req('GET', f'/api/jobs/{job_id}')
        print(f"[{tag}] status={job.get('status')} progress={job.get('progress')} step={job.get('current_step')}", flush=True)
        if job.get('status') in ('completed', 'failed', 'cancelled'):
            return job
        time.sleep(5)

job_generate = req('POST', f'/api/projects/{PROJECT_ID}/generate', {'resolution': '1080p', 'fps': 30, 'strategy': 'complete'})
result_generate = wait_job(job_generate['id'], 'GENERATE_RETRY')
if result_generate.get('status') != 'completed':
    print('GENERATE_RETRY_FAILED', result_generate.get('error_message'))
    sys.exit(3)

chat = req('POST', f'/api/projects/{PROJECT_ID}/chat', {
    'message': '把字幕改成更醒目的黄色大字，节奏稍快一点',
    'apply': True,
})
print('CHAT_STATUS', chat.get('status'), 'JOB', chat.get('job_id'), flush=True)
if chat.get('job_id'):
    result_chat = wait_job(chat['job_id'], 'CHAT_REGEN_RETRY')
    if result_chat.get('status') != 'completed':
        print('CHAT_REGEN_RETRY_FAILED', result_chat.get('error_message'))
        sys.exit(4)

versions = req('GET', f'/api/projects/{PROJECT_ID}/versions')
print('VERSIONS', len(versions), flush=True)
if versions:
    latest = versions[0]
    print('LATEST_VERSION', latest['id'], latest['version_number'], flush=True)
    print('FILES', json.dumps({k: latest.get(k) for k in [
        'preview_url', 'draft_url', 'timeline_url', 'hyperframes_url',
        'subtitles_url', 'cover_url', 'publish_copy_url'
    ]}, ensure_ascii=False), flush=True)

print('RETRY_DONE', PROJECT_ID, flush=True)
