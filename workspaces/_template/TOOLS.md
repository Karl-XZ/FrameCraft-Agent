# FrameCraft Agent 工具



所有命令在 **项目 workspace 目录** 下执行。环境变量已由后端注入：



- `FRAMECRAFT_PROJECT_ID`

- `FRAMECRAFT_JOB_ID`（analyze/generate/regenerate 任务）

- `FRAMECRAFT_PROJECT_ROOT`



Python 与工具路径见 `STATE.json` 的 `python` 字段。



## 命令前缀（跨平台 / Codex exec）

在 **workspace 根目录** 执行。以 `STATE.json.tool_command` 为准：



```powershell
cmd /c framecraft-tool.cmd read_state
cmd /c framecraft-tool.cmd job_progress --progress 10 --step "开始分析"
cmd /c framecraft-tool.cmd analyze_assets
```

```bash
./framecraft-tool.sh read_state
./framecraft-tool.sh job_progress --progress 10 --step "开始分析"
./framecraft-tool.sh analyze_assets

```



**禁止**使用 `$PY`、裸 `python` 路径或未引用的含空格路径；一律用 `STATE.json.tool_command ...`。
**禁止**直接访问 `outputs/...` 相对路径（会从 workspace 下错误解析）。
产物路径以 `STATE.json` 为准：

- `project_root`：仓库根目录
- `outputs_dir`：`{project_root}/outputs/{project_id}/`（分析产物、版本目录 `ver_*` 都在这里）
- `uploads_dir`：素材目录
- `version_dir`：以 `build_timeline` 工具 stdout JSON 里的 `version_dir` 为准（绝对路径）

读取状态一律：`STATE.json.tool_command read_state`

## 工具列表



| 命令 | 说明 |

|------|------|

| `job_progress --progress N --step "步骤名"` | 更新任务进度（必须真实） |

| `read_state` | 读取 STATE + 分析目录状态（含 `assets_with_user_notes`、`manifest_assets`） |

| `analyze_assets` | ASR/VLM 分析素材 → asset_manifest.json |

| `write_edit_plan --file plan.json` | 写入剪辑方案 |

| `suggest_edit_plan [--strategy complete] [--platform douyin] [--draft-file strategy_draft.json]` | 将 Agent 策略草案结构化落盘为 edit_plan（推荐） |

| `build_timeline [--resolution 1080p] [--fps 30]` | 构建 unified_timeline.json |

| `write_hyperframes_design --version-dir PATH [--file design.json]` | 写入 Codex 针对当前视频设计的 HyperFrames 视觉规格 |

| `build_hyperframes --version-dir PATH` | **从 unified_timeline 生成 HyperFrames 工程（成片必用）** |

| `read_timeline` | 当前成片 timeline 摘要 |

| `apply_patch --patch-file patch.json` | 应用 Agent 自己写出的 patch 到新 version_dir |

| `write_chat_result` | stdin JSON → CHAT_RESULT.json |

| `write_visual_review --version-dir PATH [--file review.json]` | Codex 观看附加截图后写入 agent_visual_review.json |



> **已禁用（Agent 勿调用）**：`workflow_build`、`list_workflows`、`export_draft`、`render_preview`、`finalize_version` — 渲染/注册/草稿导出由服务端在 Agent 完成后自动执行。



## 示例



```bash

cd backend

venv\Scripts\python.exe -m app.services.agent_tools read_state

venv\Scripts\python.exe -m app.services.agent_tools job_progress --progress 10 --step "开始分析"

venv\Scripts\python.exe -m app.services.agent_tools analyze_assets

```



stdout 均为 JSON。失败时 exit code 非 0。

## `hyperframes_design.json` 规格要点

`generate` 阶段必须先 `build_timeline`，再写 `hyperframes_design.json`，最后 `build_hyperframes`。禁止跳过设计规格直接套用固定 translator；缺少设计规格时应直接失败，不能兜底伪装。

推荐字段：

- `layout`：`fullscreen` / `speaker_right` / `speaker_top` / `speaker_center`
- `caption`：必须居中，建议包含 `bottom`、`max_width`、`font_size`、`highlight_terms`
- `video`：人物框位置、`object_position`、`scale`，必须避开脸部和嘴部遮挡
- `palette`：当前视频调性的主色、强调色、背景色
- `ambient`：背景动效开关，非全屏版建议开启
- `blocks`：Codex 针对内容设计的动画块；每块必须有 `kind`、`start`、`duration`、`position`、可见中文文案
- `sources`：若使用外部数据引用，左下角小字列出处

可用 block 类型包括：`flow`、`compare`、`table`、`timeline`、`metric`、`quote`、`reaction`、`meme`、`sticker`、`text_card`。

视觉硬规则：

- 动画位置要随构图变化，不能大部分堆在同一角落；也不能机械排成上中下或左右队列。
- 每个 block 都要在真实渲染截图中做主观审美检查：如果看起来不高级、不自然、不符合人物动作/视线/留白，即使没有遮挡也要重做。
- `surface=transparent` / `background=false` 用于无底色贴纸、表情、梗图；需要卡片时优先半透明 `surface=soft/subtle`。
- 所有方框必须真实圆角，不能靠方形外层 wrapper 假装圆角。
- 渲染后服务端会输出 `qa_frames/agent_blocks/index.json` 和逐 block 截图，并把截图作为图片输入附加给 Codex `visual_review`；`agent_visual_review.json` 不通过时，Codex 必须重写设计并重建 HyperFrames。

硬性文字规则：所有可见文字使用简体中文；禁止出现 `FrameCraft`、`帧造`、`高级口播`、`观点重构`、`AI 重构`、`主口播原片`、`DISTRIBUTION EXPERIMENT BOARD`、`CREATOR`、`不整块解释` 等制作侧词汇；叠加文案尽量不要使用“不是……而是……”句式。

对话改片规则：Agent 必须 `read_timeline` 后自行写 patch JSON，并通过 `write_chat_result` 返回 `status=proposed`。提案阶段不要调用 `apply_patch`；用户确认后由后端 `/apply-patch` 与 `chat_regenerate` 应用并真实渲染。禁止使用 `apply_patch --message` 作为兜底决策。
