"""剪映 / CapCut 草稿导出（需求 §9）。

提供 DraftExporter 抽象接口 + 基于 VectCutAPI 的实现，避免强绑定单一工具。
把 unified_timeline.json 的元素写入剪映草稿：
- 视频 / 图片 / 音频 / 标题 / 字幕 原生可编辑
- 视频转场、轻微缩放关键帧
- 复杂动效（进度条等 baked_overlay）按导出策略跳过
导出后产出自包含的 dfd_ 草稿文件夹、draft.zip 与 draft_import_guide.md。
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path
from typing import Protocol

from ..config import IS_CAPCUT_ENV, JIANYING_DRAFT_DIR, VECTCUT_DIR
from ..utils import read_json

# 通用 → 环境特定枚举映射
_TRANSITION = {
    True: {"dissolve": "Dissolve", "slide_up": "Pull_in"},      # CapCut
    False: {"dissolve": "叠化", "slide_up": "上移"},             # 剪映
}
_TEXT_INTRO = {True: {"fade_in": "Fade_In", "slide_in": "Slide_In"}, False: {}}
_TEXT_OUTRO = {True: {"fade_out": "Fade_Out"}, False: {}}
_IMG_INTRO = {True: {"zoom_in": "Zoom_In", "fade_in": "Fade_In"}, False: {}}


def _ensure_vectcut_path() -> None:
    p = str(VECTCUT_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


class DraftExportResult:
    def __init__(self, zip_path: Path, draft_folder: Path | None, copied_to: Path | None, guide: Path):
        self.zip_path = zip_path
        self.draft_folder = draft_folder
        self.copied_to = copied_to
        self.guide = guide


class ValidationResult:
    def __init__(self, ok: bool, errors: list[str], warnings: list[str] | None = None):
        self.ok = ok
        self.errors = errors
        self.warnings = warnings or []

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


class DraftExporter(Protocol):
    name: str
    supported_targets: list[str]

    def export_draft(self, timeline: dict, out_dir: Path) -> DraftExportResult: ...

    def validate_draft(self, path: Path) -> ValidationResult: ...


class VectCutDraftExporter:
    """基于 VectCutAPI / pyJianYingDraft 的剪映 / CapCut 草稿导出器。"""

    name = "vectcut"
    supported_targets = ["jianying", "capcut"]

    def export_draft(self, timeline: dict, out_dir: Path) -> DraftExportResult:
        _ensure_vectcut_path()
        from add_audio_track import add_audio_track
        from add_image_impl import add_image_impl
        from add_text_impl import add_text_impl
        from add_video_keyframe_impl import add_video_keyframe_impl
        from add_video_track import add_video_track
        from create_draft import create_draft
        from save_draft_impl import save_draft_impl

        out_dir.mkdir(parents=True, exist_ok=True)
        project = timeline["project"]
        width, height = project["width"], project["height"]
        assets_by_id = {a["asset_id"]: a for a in timeline.get("assets", [])}

        target = JIANYING_DRAFT_DIR if JIANYING_DRAFT_DIR.exists() else out_dir
        target = Path(target)

        _, draft_id = create_draft(width=width, height=height)
        editable: list[str] = []
        baked: list[str] = []

        for item in timeline.get("items", []):
            mode = item.get("draft_export_mode", "native")
            if mode in {"baked_overlay", "baked_video", "hyperframes_only"}:
                baked.append(f"{item.get('role', item.get('type'))}")
                continue

            itype = item.get("type")
            aid = item.get("asset_id")
            src = assets_by_id.get(aid, {}).get("file_path") if aid else None
            start = float(item.get("timeline_start", 0))
            end = float(item.get("timeline_end", start + 1))
            dur = max(0.1, end - start)
            try:
                if itype == "video" and src:
                    transition = None
                    tr = item.get("transition")
                    if tr:
                        transition = _TRANSITION[IS_CAPCUT_ENV].get(tr.get("type"))
                    track = "main" if item.get("role") == "a_roll" else "broll"
                    add_video_track(
                        video_url=src,
                        draft_folder=str(target),
                        start=float(item.get("source_start", 0)),
                        end=float(item.get("source_end", dur)),
                        target_start=start,
                        draft_id=draft_id,
                        width=width,
                        height=height,
                        track_name=track,
                        transition=transition,
                        transition_duration=(tr or {}).get("duration", 0.4) if tr else 0.4,
                        volume=1.0 if item.get("role") == "a_roll" else 0.0,
                    )
                    # 轻微缩放 → 剪映关键帧（native_keyframe）
                    if item.get("animations"):
                        for a in item["animations"]:
                            if a.get("type") == "scale":
                                try:
                                    add_video_keyframe_impl(
                                        draft_id=draft_id,
                                        track_name=track,
                                        property_types=["uniform_scale", "uniform_scale"],
                                        times=[start, end],
                                        values=[str(a.get("from", 1.0)), str(a.get("to", 1.06))],
                                    )
                                except Exception:
                                    pass
                    editable.append("视频片段")
                elif itype == "image" and src:
                    intro = _IMG_INTRO[IS_CAPCUT_ENV].get(item.get("intro_animation"))
                    add_image_impl(
                        draft_id=draft_id,
                        image_url=src,
                        start=start,
                        end=end,
                        draft_folder=str(target),
                        width=width,
                        height=height,
                        intro_animation=intro,
                    )
                    editable.append("图片")
                elif itype == "subtitle":
                    add_text_impl(
                        text=item.get("text", ""),
                        start=start,
                        end=end,
                        draft_id=draft_id,
                        transform_y=-0.62,
                        font_color="#FFFFFF",
                        font_size=float(item.get("font_size", 10.0)),
                        border_color="#000000",
                        border_width=8.0,
                        track_name="subtitle",
                        width=width,
                        height=height,
                        fixed_width=0.8,
                    )
                    editable.append("字幕文本")
                elif itype == "text" and item.get("role") == "hook":
                    add_text_impl(
                        text=item.get("text", ""),
                        start=start,
                        end=end,
                        draft_id=draft_id,
                        transform_y=0.66,
                        font_color="#FACC15",
                        font_size=15.0,
                        border_color="#000000",
                        border_width=6.0,
                        track_name="title",
                        intro_animation=_TEXT_INTRO[IS_CAPCUT_ENV].get(item.get("intro_animation")),
                        outro_animation=_TEXT_OUTRO[IS_CAPCUT_ENV].get(item.get("outro_animation")),
                        width=width,
                        height=height,
                    )
                    editable.append("标题文本")
                elif itype == "text" and item.get("role") == "lower_third":
                    txt = item.get("text", "")
                    if item.get("subtitle"):
                        txt = f"{txt}\n{item['subtitle']}"
                    add_text_impl(
                        text=txt,
                        start=start,
                        end=end,
                        draft_id=draft_id,
                        transform_x=-0.32,
                        transform_y=-0.32,
                        font_color="#FFFFFF",
                        font_size=7.0,
                        background_color="#0D1321",
                        background_alpha=0.6,
                        track_name="lower_third",
                        width=width,
                        height=height,
                    )
                    editable.append("信息条文本")
                elif itype == "text" and item.get("role") == "chapter_card":
                    add_text_impl(
                        text=item.get("text", ""),
                        start=start,
                        end=end,
                        draft_id=draft_id,
                        transform_y=0.1,
                        font_color="#FFFFFF",
                        font_size=12.0,
                        border_color="#000000",
                        border_width=6.0,
                        track_name="title",
                        width=width,
                        height=height,
                    )
                    editable.append("章节标题文本")
                elif itype == "text" and item.get("role") == "explainer_card":
                    txt = item.get("text", "")
                    if item.get("body"):
                        txt = f"{txt}\n{item['body']}"
                    add_text_impl(
                        text=txt,
                        start=start,
                        end=end,
                        draft_id=draft_id,
                        transform_y=0.2,
                        font_color="#FFFFFF",
                        font_size=8.0,
                        background_color="#07121C",
                        background_alpha=0.7,
                        track_name="title",
                        width=width,
                        height=height,
                        fixed_width=0.7,
                    )
                    editable.append("图文解释卡文本")
                elif itype == "text" and item.get("role") == "cta":
                    add_text_impl(
                        text=item.get("text", ""),
                        start=start,
                        end=end,
                        draft_id=draft_id,
                        transform_y=0.0,
                        font_color="#FFFFFF",
                        font_size=14.0,
                        border_color="#000000",
                        border_width=6.0,
                        track_name="title",
                        width=width,
                        height=height,
                        fixed_width=0.8,
                    )
                    editable.append("结尾 CTA 文本")
                elif itype == "audio" and src:
                    is_sfx = item.get("role") == "sfx"
                    add_audio_track(
                        audio_url=src,
                        draft_folder=str(target),
                        start=float(item.get("source_start", 0)),
                        end=float(item.get("source_end", dur)),
                        target_start=start,
                        draft_id=draft_id,
                        volume=float(item.get("volume", 0.6 if is_sfx else 0.25)),
                        track_name="sfx" if is_sfx else "bgm",
                        width=width,
                        height=height,
                    )
                    editable.append("音效" if is_sfx else "背景音乐")
            except Exception:
                continue

        save_draft_impl(draft_id=draft_id, draft_folder=str(target))

        src_folder = VECTCUT_DIR / draft_id
        self._self_contain_assets(src_folder)

        export_folder = out_dir / draft_id
        if src_folder.exists():
            if export_folder.exists():
                shutil.rmtree(export_folder)
            shutil.copytree(src_folder, export_folder)

        copied_to = None
        if target != out_dir and target.exists() and src_folder.exists():
            dest = target / draft_id
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src_folder, dest)
            copied_to = dest

        # 清理 VectCutAPI 工作目录的临时草稿
        if src_folder.exists():
            shutil.rmtree(src_folder, ignore_errors=True)

        zip_path = out_dir / "draft.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if export_folder.exists():
                for p in export_folder.rglob("*"):
                    if p.is_file():
                        zf.write(p, p.relative_to(out_dir))

        guide = self._write_guide(out_dir, draft_id, editable, baked, copied_to)
        return DraftExportResult(zip_path, export_folder if export_folder.exists() else None, copied_to, guide)

    def validate_draft(self, path: Path) -> ValidationResult:
        """校验生成的草稿是否结构完整、素材可用（需求 §9.2 DraftExporter.validateDraft）。"""
        errors: list[str] = []
        warnings: list[str] = []
        path = Path(path)
        if not path.exists():
            return ValidationResult(False, [f"草稿路径不存在: {path}"])

        # 允许传入版本 draft 目录：自动定位其中的 dfd_/草稿子目录
        folder = path
        if (path / "draft_info.json").exists() or (path / "draft_content.json").exists():
            folder = path
        else:
            subdirs = [d for d in path.iterdir() if d.is_dir() and (
                (d / "draft_info.json").exists() or (d / "draft_content.json").exists()
            )]
            if subdirs:
                folder = subdirs[0]
            else:
                errors.append("未找到 draft_info.json / draft_content.json，草稿可能未正确生成")
                return ValidationResult(False, errors)

        info_file = folder / "draft_info.json"
        if not info_file.exists():
            info_file = folder / "draft_content.json"
        try:
            data = read_json(info_file)
        except Exception as exc:
            return ValidationResult(False, [f"草稿元数据解析失败: {exc}"])

        materials = data.get("materials", {}) or {}
        media_count = 0
        for key in ("videos", "audios"):
            for m in materials.get(key, []) or []:
                media_count += 1
                name = m.get("material_name")
                remote = m.get("remote_url")
                mtype = m.get("material_type") or m.get("type") or ""
                sub = "audio" if key == "audios" else ("image" if mtype == "photo" else "video")
                local = folder / "assets" / sub / name if name else None
                ok_local = bool(local and local.exists())
                ok_remote = bool(remote and Path(remote).exists())
                if not (ok_local or ok_remote):
                    warnings.append(f"素材文件缺失，导入后可能离线不可用: {name or remote}")
        if media_count == 0:
            warnings.append("草稿中没有任何视频 / 音频素材")

        tracks = data.get("tracks", []) or []
        if not tracks:
            errors.append("草稿没有任何轨道")

        return ValidationResult(len(errors) == 0, errors, warnings)

    def _self_contain_assets(self, src_folder: Path) -> None:
        """把素材本体复制进草稿的 assets 目录，使草稿自包含、可离线导入。"""
        info = src_folder / "draft_info.json"
        if not info.exists():
            return
        try:
            data = read_json(info)
        except Exception:
            return
        materials = data.get("materials", {})
        groups = [("audios", "audio"), ("videos", "video")]
        for key, _ in groups:
            for m in materials.get(key, []) or []:
                remote = m.get("remote_url")
                name = m.get("material_name")
                mtype = m.get("material_type") or m.get("type") or ""
                sub = "audio" if key == "audios" else ("image" if mtype == "photo" else "video")
                if not (remote and name):
                    continue
                src = Path(remote)
                if not src.exists():
                    continue
                dest = src_folder / "assets" / sub / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    try:
                        shutil.copy2(src, dest)
                    except Exception:
                        pass

    def _write_guide(self, out_dir: Path, draft_id: str, editable, baked, copied_to) -> Path:
        env = "CapCut 国际版" if IS_CAPCUT_ENV else "剪映专业版"
        editable_set = sorted(set(editable))
        baked_set = sorted(set(baked))
        guide = out_dir / "draft_import_guide.md"
        guide.write_text(
            f"""# 剪映 / CapCut 草稿导入说明

- 草稿 ID：`{draft_id}`
- 推荐软件：**{env}**（与生成环境一致）
- 已自动复制到草稿目录：{'是 → ' + str(copied_to) if copied_to else '否（请手动复制）'}

## 导入步骤
1. 解压 `draft.zip`，得到 `{draft_id}/` 文件夹；
2. 将整个文件夹复制到 {env} 草稿目录：
   `%LOCALAPPDATA%\\{'CapCut' if IS_CAPCUT_ENV else 'JianyingPro'}\\User Data\\Projects\\com.lveditor.draft`
3. **重启 {env}**，在草稿列表中打开。

## 可原生编辑的元素
{chr(10).join(f'- {e}' for e in editable_set) or '- （无）'}

## 渲染为覆盖层 / 仅预览的元素（草稿中降级或省略）
{chr(10).join(f'- {b}' for b in baked_set) or '- （无）'}

> 复杂 CSS / 进度条等动效无法在剪映原生编辑，已按导出策略烘焙或省略；
> 高级动画效果请以 HyperFrames 预览视频为准。
""",
            encoding="utf-8",
        )
        return guide


_EXPORTER: DraftExporter = VectCutDraftExporter()


def export_draft(timeline: dict, out_dir: Path) -> tuple[Path, Path | None]:
    """兼容旧调用签名：返回 (zip_path, copied_to)。"""
    result = _EXPORTER.export_draft(timeline, out_dir)
    return result.zip_path, result.copied_to


def validate_draft(path: Path) -> ValidationResult:
    """校验草稿目录，供任务流程与 API 复用（需求 §9.2 / §24.2）。"""
    return _EXPORTER.validate_draft(path)
