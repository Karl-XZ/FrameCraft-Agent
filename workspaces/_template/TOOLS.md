# FrameCraft Agent 工具

所有命令在 **项目 workspace 目录** 下执行。环境变量已由后端注入：

- `FRAMECRAFT_PROJECT_ID`
- `FRAMECRAFT_JOB_ID`（analyze/generate/regenerate 任务）
- `FRAMECRAFT_PROJECT_ROOT`

Python 与工具路径见 `STATE.json` 的 `python` 字段。

## 命令前缀（Windows / OpenClaw exec）

在 **workspace 根目录**（含 STATE.json、framecraft-tool.cmd）执行：

```powershell
cmd /c framecraft-tool.cmd read_state
cmd /c framecraft-tool.cmd job_progress --progress 10 --step "开始分析"
cmd /c framecraft-tool.cmd analyze_assets
```

**禁止**使用 `$PY`、裸 `python` 路径或未引用的含空格路径；一律用 `cmd /c framecraft-tool.cmd ...`。

## 工具列表

| 命令 | 说明 |
|------|------|
| `job_progress --progress N --step "步骤名"` | 更新任务进度（必须真实） |
| `read_state` | 读取 STATE + 分析目录状态 |
| `analyze_assets` | ASR/VLM 分析素材 → asset_manifest.json |
| `write_edit_plan --file plan.json` | 写入剪辑方案 |
| `suggest_edit_plan [--strategy complete] [--platform douyin]` | LLM 辅助生成方案（可选） |
| `build_timeline [--resolution 1080p] [--fps 30]` | 构建 unified_timeline.json |
| `list_workflows` | 列出口播 HyperFrames 工作流 |
| `workflow_build --version-dir PATH --workflow-id ID` | 执行口播工作流 build |
| `render_preview --version-dir PATH --hyperframes-dir PATH` | 渲染 preview.mp4 |
| `export_draft --version-dir PATH` | 导出剪映草稿 |
| `finalize_version --version-dir PATH [--hyperframes-dir PATH]` | 字幕/封面/注册版本 |
| `read_timeline` | 当前成片 timeline 摘要 |
| `apply_patch --message "用户改片指令"` | 应用 patch 到新 version_dir |
| `write_chat_result` | stdin JSON → CHAT_RESULT.json |

## 示例

```bash
cd backend
venv\Scripts\python.exe -m app.services.agent_tools read_state
venv\Scripts\python.exe -m app.services.agent_tools job_progress --progress 10 --step "开始分析"
venv\Scripts\python.exe -m app.services.agent_tools analyze_assets
```

stdout 均为 JSON。失败时 exit code 非 0。
