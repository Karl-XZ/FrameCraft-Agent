# 帧造 Agent（FrameCraft Agent）

> AI 口播视频智能重构工作台 — 由 **OpenClaw Agent** 编排制片流程，上传口播与素材后自动分析、剪辑，生成 HyperFrames 高级预览视频，并同步导出可编辑的剪映 / CapCut 草稿。

[![GitHub](https://img.shields.io/badge/GitHub-Karl--XZ%2FFrameCraft--Agent-blue)](https://github.com/Karl-XZ/FrameCraft-Agent)

---

## 目录

- [项目简介](#项目简介)
- [核心能力](#核心能力)
- [系统架构](#系统架构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [详细安装](#详细安装)
- [配置说明](#配置说明)
- [启动项目](#启动项目)
- [使用指南](#使用指南)
- [端到端测试](#端到端测试)
- [项目结构](#项目结构)
- [常见问题](#常见问题)
- [相关文档](#相关文档)

---

## 项目简介

**帧造 Agent** 是一个端到端的 AI 口播视频重构平台。与「固定脚本流水线」不同，本项目的 **analyze / generate / chat_regenerate / 对话改片** 全部由 **OpenClaw Agent** 驱动：

1. Agent 阅读项目工作区（`AGENTS.md`、`TOOLS.md`、`STATE.json`）
2. 自主规划并调用 `framecraft-tool` 原子工具（ASR、分析、建时间线、渲染、导出草稿）
3. 产出 `unified_timeline.json` 作为唯一事实来源
4. HyperFrames 渲染高级预览 + VectCutAPI 同步剪映草稿
5. 用户可在 Web 端预览、下载，或与 Agent 对话迭代修改

核心交付：**OpenClaw 可观测制片决策 + 预览视频 + 剪映草稿 + 可迭代 Agent 工作流**。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **OpenClaw 编排** | 分析、生成、对话改片均经 `openclaw agent --local`，禁止后端固定流水线 |
| 多素材上传 | 口播视频、B-roll、图片、音频、Logo，支持标签与备注 |
| Agent 工具链 | `agent_tools` CLI：ASR、faster-whisper、素材分析、剪辑方案、时间线、渲染、草稿导出 |
| 口播工作流 | 三套 HyperFrames 口播模板自动选型（竖屏/居左横版/全屏横版） |
| 视频生成 | HyperFrames 渲染 + legacy 兜底 + FFmpeg 应急预览 |
| 草稿导出 | VectCutAPI → 剪映 `dfd_*` 草稿 |
| Agent 对话 | 自然语言改片 → timeline patch → 用户确认后重新生成 |
| 版本管理 | 每次生成/修改产生 v1、v2…，可预览与下载 |

---

## 系统架构

```text
用户（Web 前端 React）
        ↓
FastAPI 后端（任务队列 + SSE 进度 + 文件服务）
        ↓
OpenClaw Agent（每项目独立 workspace + agent）
        ↓ exec framecraft-tool.cmd
agent_tools CLI（analyze_assets / build_timeline / render_preview / …）
        ↓
Python 服务层（ASR、analyzer、planner、HyperFrames、VectCutAPI）
        ↓
unified_timeline.json
        ├── HyperFrames → preview.mp4
        └── VectCutAPI  → 剪映草稿
        ↓
Web 预览 / 下载 / Agent 对话 → chat_regenerate
```

**技术栈：**

| 层级 | 技术 |
|------|------|
| 编排 | **OpenClaw** 2026.6+（`openclaw agent --local`） |
| 前端 | React 19 + TypeScript + Vite + Tailwind + Zustand |
| 后端 | FastAPI + SQLite + 后台 JobRunner |
| Agent 工具 | `backend/app/services/agent_tools`（JSON CLI） |
| 渲染 | HyperFrames + Chromium + FFmpeg |
| 草稿 | VectCutAPI（pyJianYingDraft） |
| ASR | faster-whisper（本地）/ 云端 API（可选） |
| LLM | OpenAI 兼容 API（**必须配置 Key**，供 OpenClaw 调用） |

**健康检查示例**（http://127.0.0.1:8000/api/health）：

```json
{
  "status": "ok",
  "orchestrator": "openclaw",
  "openclaw": true,
  "chat_engine": "openclaw-agent",
  "pipeline": "agent-only",
  "build": "2026-06-16-openclaw"
}
```

---

## 环境要求

### 硬件建议

- **操作系统：** Windows 10/11（本文以 Windows 为例；Docker 见 `docker-compose.yml`）
- **CPU / 内存：** 8 核、32GB RAM（推荐）
- **磁盘：** 200GB SSD
- **网络：** GitHub、npm、模型 API（DashScope / OpenAI 等）

### 必备软件

| 软件 | 版本 | 用途 |
|------|------|------|
| **Node.js** | ≥ 22.19 | OpenClaw、HyperFrames、前端 |
| **OpenClaw** | ≥ 2026.6 | Agent 编排（**必须**） |
| **Python** | ≥ 3.10 | 后端、agent_tools、VectCutAPI、ASR |
| **FFmpeg** | 8.x | 音视频处理 |
| **Git** | 较新版本 | 克隆仓库 |
| **大模型 API Key** | — | OpenClaw 调用 LLM（**必须**） |
| 剪映 / CapCut | 已安装 | 草稿导入验证（可选） |

> 完整环境步骤见 [`准备工作.md`](准备工作.md)。

---

## 快速开始

```powershell
# 1. 克隆
git clone https://github.com/Karl-XZ/FrameCraft-Agent.git
cd FrameCraft-Agent

# 2. 安装 OpenClaw（全局）
npm install -g openclaw@latest
openclaw --version    # 期望 OpenClaw 2026.6.x

# 3. 安装 HyperFrames + 前端依赖
npm install
cd framecraft-agent && npm install && cd ..

# 4. 后端 venv
python -m venv backend\venv
backend\venv\Scripts\activate
pip install -r backend\requirements.txt

# 5. 配置 API Key（任选其一）
#    a) 启动后在 Web「模型设置」填写
#    b) 环境变量：
$env:LLM_API_KEY = "你的-key"
$env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 6. 启动（两个终端）
scripts\start-backend.bat
scripts\start-frontend.bat

# 7. 打开工作台
# http://127.0.0.1:5173/studio
```

确认 `http://127.0.0.1:8000/api/health` 中 `"openclaw": true`。

---

## 详细安装

### 1. Node.js（≥ 22.19）与 PATH

```powershell
node --version   # >= v22.19.0
where.exe node   # 不得指向 Python312\Scripts\node.exe
```

### 2. OpenClaw

```powershell
npm install -g openclaw@latest
openclaw --version
```

每个 FrameCraft 项目在 `workspaces/<project_id>/` 拥有独立 OpenClaw Agent workspace，模板见 `workspaces/_template/`。

### 3. HyperFrames

```powershell
npm install
npx hyperframes --version
```

### 4. 后端 Python 依赖

```powershell
python -m venv backend\venv
backend\venv\Scripts\activate
pip install -r backend\requirements.txt
```

### 5. VectCutAPI（剪映草稿）

```powershell
cd vendor\VectCutAPI
python -m venv venv-capcut
.\venv-capcut\Scripts\activate
pip install -r requirements.txt
cd ..\..
```

### 6. 本地 ASR（推荐）

```powershell
python -m venv vendor\asr-venv
.\vendor\asr-venv\Scripts\activate
pip install faster-whisper
```

### 7. 剪映路径

编辑 `config/local.paths.json`：

```json
{
  "jianying": {
    "draft_dir": "C:\\Users\\你\\AppData\\Local\\JianyingPro\\User Data\\Projects\\com.lveditor.draft",
    "is_capcut_env": false
  },
  "tools": {
    "node_exe": "C:\\Users\\你\\AppData\\Local\\Programs\\node-v22.20.0-win-x64\\node.exe"
  }
}
```

### 8. 环境自检

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-env.ps1
```

---

## 配置说明

### 模型 API（必须）

OpenClaw 需要大模型 API Key，否则 analyze / generate / chat 均无法启动。

| 方式 | 说明 |
|------|------|
| Web「模型设置」 | Provider、Base URL、API Key、文本/视觉模型 |
| 环境变量 | `LLM_API_KEY` / `OPENAI_API_KEY` / `DASHSCOPE_API_KEY` |
| `.env` | 复制 `config/platform.env.example` 后填写 |

推荐 DashScope（Qwen）：`base_url` = `https://dashscope.aliyuncs.com/compatible-mode/v1`，模型 `qwen-max`。

OpenClaw 配置参考：`config/openclaw.framecraft.json5`（无密钥，运行时由 `openclaw_runtime.py` patch 合并）。

### 本机路径

`config/local.paths.json` — 剪映草稿目录、Node 路径等（换机必改）。

---

## 启动项目

**终端 1 — 后端：**

```powershell
scripts\start-backend.bat
```

**终端 2 — 前端：**

```powershell
scripts\start-frontend.bat
```

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:5173/studio | 工作台 |
| http://127.0.0.1:8000/api/health | 健康检查（含 openclaw 状态） |
| http://127.0.0.1:8000/docs | API 文档 |

> Vite 首次启动约 1～2 分钟（依赖预构建）。

### Docker（可选）

```powershell
docker compose up --build
```

见 `docker-compose.yml`、`docker/backend.Dockerfile`、`docker/frontend.Dockerfile`。

---

## 口播工作流自动选型

生成时 OpenClaw Agent 调用 `list_workflows`，根据画幅与源片比例选用 `workflows/talking-head/` 模板：

| 画幅 | 源片 | workflow_id |
|------|------|-------------|
| 16:9 | 横屏 | `landscape_left` |
| 16:9 | 竖屏 | `fullscreen_landscape` |
| 9:16 | 默认 | `vertical_pip` |

详见 `workflows/talking-head/README.md` 与三份中文工作流文档。

---

## 使用指南

### 五步工作流

```text
① 上传素材 → ② AI 分析 → ③ 剪辑方案 → ④ 生成视频 → ⑤ 导出修改
```

1. **上传**：口播（必须）+ B-roll / 图片 / BGM / Logo，填写标签备注
2. **分析**：触发 OpenClaw `analyze` 任务 → 产出 `asset_manifest.json`、`edit_plan.json`
3. **方案**：Web 展示剪辑方案，确认后生成
4. **生成**：OpenClaw `generate` → 时间线 + HyperFrames 预览 + 剪映草稿
5. **修改**：右侧 Agent 对话 → 生成 patch → 用户确认 → `chat_regenerate`

### Agent 对话改片

- 闲聊：Agent 直接中文回复
- 改片指令（如「字幕渐显渐隐」）：Agent 调用 `read_timeline` → `apply_patch` → `write_chat_result`
- 前端展示 patch 卡片，用户 **接受** 后才触发重新生成

### 剪映导入

1. 下载草稿 ZIP，解压 `dfd_*` 文件夹
2. 复制到 `com.lveditor.draft` 目录
3. 重启剪映

---

## 端到端测试

```powershell
# API 流水线（需后端已启动 + 已配置 API Key）
backend\venv\Scripts\activate
pip install httpx
python scripts\run_e2e_test.py

# 真实口播素材 nov26 + OpenClaw session 日志采集
python scripts\run_nov26_e2e.py

# 对话接口冒烟
python scripts\test_chat_e2e.py

# 采集 OpenClaw 决策轨迹
python scripts\collect_openclaw_sessions.py <project_id>
```

任务日志：`outputs/<project_id>/logs/<job_id>.log`

---

## 项目结构

```text
FrameCraft-Agent/
├── README.md
├── 准备工作.md
├── package.json                         # HyperFrames
├── config/
│   ├── local.paths.json
│   ├── platform.env.example
│   └── openclaw.framecraft.json5
├── workspaces/
│   └── _template/                       # OpenClaw Agent 工作区模板
│       ├── AGENTS.md                    # 制片员指令
│       ├── TOOLS.md                     # framecraft-tool 命令表
│       └── framecraft-tool.cmd
├── backend/app/
│   ├── main.py
│   ├── routers/
│   └── services/
│       ├── openclaw_runtime.py          # OpenClaw CLI 封装（唯一编排入口）
│       ├── job_runner.py                # 仅 dispatch OpenClaw
│       ├── chat_service.py              # 对话走 OpenClaw
│       ├── agent_tools/                 # Agent 原子工具 CLI
│       ├── talking_head_workflow_service.py
│       ├── analyzer.py / planner.py / hyperframes_service.py / draft_service.py
│       └── ...
├── framecraft-agent/                    # React 前端
├── workflows/talking-head/              # 三套口播 HyperFrames 工作流
├── scripts/
│   ├── start-backend.bat / start-frontend.bat
│   ├── verify-env.ps1
│   ├── run_e2e_test.py
│   ├── run_nov26_e2e.py
│   └── collect_openclaw_sessions.py
├── vendor/VectCutAPI/
├── docker-compose.yml
├── uploads/   outputs/   workspaces/    # 运行时目录（git 忽略，除 _template）
```

### 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 含 `openclaw` 布尔状态 |
| POST | `/api/projects/{id}/assets/analyze` | 提交 OpenClaw analyze 任务 |
| POST | `/api/projects/{id}/generate` | 提交 OpenClaw generate 任务 |
| POST | `/api/projects/{id}/chat` | OpenClaw 对话 / patch 提案 |
| GET | `/api/jobs/{id}/events` | SSE 进度（含 Agent 日志） |
| GET/PUT | `/api/settings/model` | 模型配置（同步至 OpenClaw） |

---

## 常见问题

### Q1：`openclaw: false` 或任务立即失败

```powershell
npm install -g openclaw@latest
where.exe node          # 确保真实 Node，非 Python 假 node.exe
openclaw --version
```

### Q2：提示「未配置大模型 API Key」

在 Web「模型设置」填写 Key，或设置环境变量 `LLM_API_KEY`，重启后端。

### Q3：`node --version` 报 `No module named 'nodejs_wheel'`

Python `Scripts\node.exe` 遮蔽了 Node。将 Node 安装目录置于 PATH 最前。

### Q4：分析/生成失败，日志显示 Agent 未产出文件

查看 `outputs/<project_id>/logs/`。常见原因：API 超时、OpenClaw 未调用 `framecraft-tool`、HyperFrames 渲染失败。Agent 须在 workspace 内按 `AGENTS.md` 调用工具链。

### Q5：对话改片没有 patch

改片需已有成片版本；Agent 应调用 `apply_patch` + `write_chat_result`。若只返回闲聊，检查 Key、超时（chat 默认 120s）及 `workspaces/<id>/CHAT_RESULT.json`。

### Q6：前端首次启动慢

Vite 依赖预构建约 1～2 分钟，属正常。

### Q7：剪映看不到草稿

确认 `dfd_*` 在 `com.lveditor.draft` 下，重启剪映，`is_capcut_env` 与软件一致。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [`准备工作.md`](准备工作.md) | 环境搭建 |
| [`帧造_Agent_项目需求文档(2).md`](帧造_Agent_项目需求文档(2).md) | 需求规格 |
| [`workflows/talking-head/README.md`](workflows/talking-head/README.md) | 口播工作流 |
| [OpenClaw 文档](https://docs.openclaw.ai/) | Agent 运行时 |
| [HyperFrames](https://hyperframes.heygen.com/) | 视频渲染 |
| [VectCutAPI](https://github.com/sun-guannan/VectCutAPI) | 剪映草稿 |

---

如有问题，欢迎在 [GitHub Issues](https://github.com/Karl-XZ/FrameCraft-Agent/issues) 反馈。
