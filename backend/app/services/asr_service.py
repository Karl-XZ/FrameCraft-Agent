from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import ASR_VENV_PYTHON, ROOT
from ..utils import run_cmd, write_json


def transcribe_audio(audio_path: Path, work_dir: Path, model_size: str = "base") -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    out_prefix = work_dir / "asr"
    script = f"""
import json
from pathlib import Path
from faster_whisper import WhisperModel

audio = Path(r"{audio_path}")
model = WhisperModel("{model_size}", device="cpu", compute_type="int8")
segments, info = model.transcribe(str(audio), word_timestamps=True, vad_filter=True)

words = []
segments_out = []
full_text = []
for seg in segments:
    seg_words = []
    if seg.words:
        for w in seg.words:
            item = {{"word": w.word.strip(), "start": w.start, "end": w.end}}
            words.append(item)
            seg_words.append(item)
    segments_out.append({{
        "start": seg.start,
        "end": seg.end,
        "text": seg.text.strip(),
        "words": seg_words,
    }})
    full_text.append(seg.text.strip())

result = {{
    "language": info.language,
    "duration": info.duration,
    "text": " ".join(full_text).strip(),
    "segments": segments_out,
    "words": words,
}}
Path(r"{out_prefix}_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("OK")
"""
    py = ASR_VENV_PYTHON if ASR_VENV_PYTHON.exists() else Path(sys.executable)
    result = run_cmd([str(py), "-c", script], cwd=ROOT)
    if result.returncode != 0:
        raise RuntimeError(f"ASR failed: {result.stderr or result.stdout}")
    data_path = Path(f"{out_prefix}_result.json")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    write_json(work_dir / "transcript.json", {"text": data["text"], "language": data["language"]})
    write_json(work_dir / "word_timestamps.json", data["words"])
    write_json(work_dir / "speech_segments.json", data["segments"])
    return data


def build_cut_candidates(segments: list[dict]) -> list[dict]:
    candidates = []
    for seg in segments:
        text = seg.get("text", "")
        duration = seg.get("end", 0) - seg.get("start", 0)
        if duration > 1.2 and any(x in text for x in ("嗯", "啊", "那个", "就是", "然后")):
            candidates.append(
                {"start": seg["start"], "end": seg["end"], "reason": "filler", "text": text}
            )
        if duration > 2.5 and text.count(text[:2]) > 2:
            candidates.append(
                {"start": seg["start"], "end": seg["end"], "reason": "repeat", "text": text}
            )
    return candidates


def build_highlights(segments: list[dict], max_items: int = 5) -> list[dict]:
    ranked = sorted(segments, key=lambda s: len(s.get("text", "")), reverse=True)
    out = []
    for seg in ranked[:max_items]:
        out.append({"start": seg["start"], "end": seg["end"], "text": seg["text"], "score": len(seg["text"])})
    return out
