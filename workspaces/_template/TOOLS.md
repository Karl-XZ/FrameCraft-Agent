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

**禁止**用 OpenClaw 内置 `read` / `edit` 直接访问 `outputs/...` 相对路径（会从 workspace 下错误解析）。
产物路径以 `STATE.json` 为准：

- `project_root`：仓库根目录
- `outputs_dir`：`{project_root}/outputs/{project_id}/`（分析产物、版本目录 `ver_*` 都在这里）
- `uploads_dir`：素材目录
- `version_dir`：以 `build_timeline` 工具 stdout JSON 里的 `version_dir` 为准（绝对路径）

读取状态一律：`cmd /c framecraft-tool.cmd read_state`

## 工具列表



| 命令 | 说明 |

|------|------|

| `job_progress --progress N --step "步骤名"` | 更新任务进度（必须真实） |

| `read_state` | 读取 STATE + 分析目录状态（含 `assets_with_user_notes`、`manifest_assets`） |

| `analyze_assets` | ASR/VLM 分析素材 → asset_manifest.json |

| `write_edit_plan --file plan.json` | 写入剪辑方案 |

| `suggest_edit_plan [--strategy complete] [--platform douyin] [--draft-file strategy_draft.json]` | 将 Agent 策略草案结构化落盘为 edit_plan（推荐） |

| `build_timeline [--resolution 1080p] [--fps 30]` | 构建 unified_timeline.json |

| `build_hyperframes --version-dir PATH` | **从 unified_timeline 生成 HyperFrames 工程（成片必用）** |

| `read_timeline` | 当前成片 timeline 摘要 |

| `apply_patch --message "用户改片指令"` | 应用 patch 到新 version_dir |

| `write_chat_result` | stdin JSON → CHAT_RESULT.json |



> **已禁用（Agent 勿调用）**：`workflow_build`、`list_workflows`、`export_draft`、`render_preview`、`finalize_version` — 渲染/注册/草稿导出由服务端在 Agent 完成后自动执行。



## 示例



```bash

cd backend

venv\Scripts\python.exe -m app.services.agent_tools read_state

venv\Scripts\python.exe -m app.services.agent_tools job_progress --progress 10 --step "开始分析"

venv\Scripts\python.exe -m app.services.agent_tools analyze_assets

```



stdout 均为 JSON。失败时 exit code 非 0。


