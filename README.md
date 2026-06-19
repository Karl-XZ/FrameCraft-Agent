# FrameCraft Agent

FrameCraft Agent 是一个口播视频制片工作台。当前新版保留原 React 前端，后端已重做为“轻 API 外壳 + 单一 Codex supervisor agent”架构。

## 当前架构

```text
React 前端
  -> FastAPI 后端
  -> 每个任务启动一个 Codex CLI supervisor agent
  -> agent 自己分析素材、设计动画、调用 HyperFrames、截图验收、注册版本
```

后端只负责项目数据、文件上传、SSE 进度、版本文件服务和给 agent 暴露哑工具。剪辑判断、文案、动画设计、HyperFrames 工程生成和视觉复审都必须由同一个 Codex agent 在一次任务内完成。

## 关键原则

- `analyze`、`generate`、`apply_patch`、`chat` 每次任务只启动一个 Codex agent。
- 每个项目有独立 `agent_session_id`、素材目录、输出目录和聊天记录；同一项目同一时刻只允许一个运行中的 agent 任务。
- Codex agent 以 `workspace-write` 沙盒运行，工具层会阻止越界读取或写入项目外文件。
- 后端不再保留旧的固定流水线、旧 agent_tools、VectCutAPI 编排或 ASR 服务层。
- `generate` 必须由 agent 完成分析、方案、HyperFrames 真渲染、逐块截图验收和版本注册。
- 禁止 FFmpeg 拼接兜底冒充成片；FFmpeg 只可用于探测、转码、抽帧等辅助动作。
- 如果 agent 没有写出必要产物，任务直接失败，不伪装成功。

## 安装

```bash
./scripts/setup-deps.sh
```

脚本会安装：

- `backend/venv` 中的 FastAPI 后端依赖
- 项目根的 `hyperframes`
- `framecraft-agent` 前端依赖
- Codex CLI 可用性检查

## 启动

```bash
./scripts/start-backend.sh
./scripts/start-frontend.sh
```

默认新版端口：

- 后端：`http://0.0.0.0:8022`
- 前端：`http://0.0.0.0:5174`

如果只想本机访问：

```bash
FRAMECRAFT_BACKEND_HOST=127.0.0.1 FRAMECRAFT_BACKEND_PORT=8022 ./scripts/start-backend.sh
FRAMECRAFT_FRONTEND_HOST=127.0.0.1 FRAMECRAFT_FRONTEND_PORT=5174 ./scripts/start-frontend.sh
```

如果要让局域网其他电脑访问，先查本机局域网 IP，例如 macOS：

```bash
ipconfig getifaddr en0
```

然后启动后端，并给前端注入可被其他电脑访问的 API 地址：

```bash
./scripts/start-backend.sh
VITE_API_BASE_URL=http://<你的局域网IP>:8022 ./scripts/start-frontend.sh
```

其他电脑访问：

```text
http://<你的局域网IP>:5174/
```

健康检查：

```bash
curl http://127.0.0.1:8022/api/health
```

预期返回：

```json
{"ok":true,"mode":"single-codex-agent"}
```

## 任务产物门禁

`analyze` 成功前必须存在：

- `outputs/<project_id>/analysis/analysis.json`
- `outputs/<project_id>/analysis/edit_plan.json`

`generate` 和 `apply_patch` 成功前必须存在：

- 已注册的视频版本
- `preview.mp4`
- `timeline.json`
- `agent_visual_review.json`
- HyperFrames 工程痕迹，如 `hyperframes_project.zip`、`hyperframes/`、`project.tsx` 或 `src/`

缺少任意关键产物，后端会把 job 标为 `failed`，并返回失败原因。

## Agent 工具

每个 Codex 任务运行时会获得 `framecraft-tool.sh`，可调用：

- `read_state`
- `progress`
- `log`
- `write_analysis`
- `write_edit_plan`
- `create_version_dir`
- `register_version`
- `write_chat`
- `probe_media`
- `copy_file`

这些工具只读写状态或文件，不包含视频创意逻辑。

## 旧版标记

本机旧版独立前端目录：

```text
/Users/applemima111/Desktop/framecraft-agent
```

该旧版曾运行在 `5173` 端口，现已停止，并已写入 `OLD_VERSION_NOTICE.md` 标记。后续开发与对外访问都以本仓库新版为准。

## 备份

本次重做前的完整项目备份在：

```text
/Users/applemima111/framecraft/FrameCraft-Agent.backup-single-agent-20260619-010256
```

## 更多文档

- [单一 Codex agent 后端说明](docs/single-codex-agent-backend.md)
- [Codex + HyperFrames 可复现口播制片工作流](docs/codex-hyperframes-reproducible-workflow.md)
