# 帧造 Agent（FrameCraft Agent）

> AI 口播视频智能重构工作台 — 上传口播与素材，自动分析剪辑，生成 HyperFrames 高级预览视频，并同步导出可编辑的剪映 / CapCut 草稿。

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

**帧造 Agent** 是一个端到端的 AI 口播视频重构平台。用户上传口播视频和辅助素材（B-roll、图片、音频、Logo 等），系统会：

1. 自动转录口播、理解素材内容
2. 生成智能剪辑方案（删减口播、匹配 B-roll、设计字幕与节奏）
3. 输出统一时间线 `unified_timeline.json` 作为唯一事实来源
4. 通过 **HyperFrames** 渲染高级预览视频
5. 通过 **VectCutAPI** 同步生成剪映 / CapCut 可编辑草稿
6. 支持在 Web 端与 Agent 对话，修改后自动重新生成预览和草稿

核心交付不是单个 MP4，而是 **预览视频 + 剪映草稿 + 可迭代修改的 Agent 工作流**。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 多素材上传 | 支持口播视频、B-roll、图片、音频、Logo，可添加标签和备注 |
| AI 分析 | 本地 faster-whisper ASR + 规则/LLM 剪辑规划 |
| 剪辑方案 | 自动生成 hook、段落结构、B-roll 匹配、字幕样式 |
| 视频生成 | HyperFrames HTML 渲染（FFmpeg 兜底预览） |
| 草稿导出 | VectCutAPI 生成剪映 `dfd_*` 草稿，可导入继续编辑 |
| Agent 对话 | 自然语言修改（如「字幕改成黄色大字」「节奏加快」） |
| 版本管理 | 每次生成/修改产生新版本，可预览和下载 |

---

## 系统架构

```text
用户上传口播 + 素材（Web 前端）
        ↓
FastAPI 后端（分析 / 规划 / 任务队列 / SSE 进度）
        ↓
  ASR 转录 + 素材理解 + 剪辑方案
        ↓
  unified_timeline.json（唯一事实来源）
        ↓
  ├── HyperFrames → preview.mp4（高级预览）
  └── VectCutAPI  → 剪映草稿（dfd_* 文件夹）
        ↓
用户在 Web 预览 / 下载 / Agent 对话修改 → 重新生成
```

**技术栈：**

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite + Tailwind CSS + Zustand |
| 后端 | FastAPI + SQLite + 后台任务队列 |
| 渲染 | HyperFrames + Chromium + FFmpeg |
| 草稿 | VectCutAPI（pyJianYingDraft） |
| ASR | faster-whisper（本地）/ OpenAI Whisper API（可选） |
| LLM | OpenAI 兼容 API（可选，无 Key 时走规则引擎） |

---

## 环境要求

### 硬件建议

- **操作系统：** Windows 10/11（本文以 Windows 为例）
- **CPU / 内存：** 8 核、32GB RAM（推荐）
- **磁盘：** 200GB SSD 可用空间
- **网络：** 可访问 GitHub、npm registry

### 必备软件

| 软件 | 版本要求 | 用途 |
|------|----------|------|
| **Node.js** | ≥ 22.19 | HyperFrames、前端构建 |
| **Python** | ≥ 3.10 | 后端、VectCutAPI、ASR |
| **FFmpeg** | 8.x | 音视频处理、编码 |
| **Git** | 任意较新版本 | 克隆仓库 |
| **剪映专业版** 或 **CapCut** | 已安装 | 导入草稿验证 |

### 可选组件

| 组件 | 用途 |
|------|------|
| HyperFrames | 高级预览视频渲染 |
| Chromium | HyperFrames 无头浏览器（首次渲染自动下载） |
| VectCutAPI | 剪映草稿导出 |
| faster-whisper | 本地口播转录 |
| OpenClaw | Agent 编排（高级场景） |
| OpenAI API Key | LLM/VLM 增强分析（无 Key 时规则兜底） |

> 更完整的环境搭建步骤见 [`准备工作.md`](准备工作.md)。

---

## 快速开始

适合已安装 Node、Python、FFmpeg 的用户，5 分钟内本地跑起来：

```powershell
# 1. 克隆仓库
git clone https://github.com/Karl-XZ/FrameCraft-Agent.git
cd FrameCraft-Agent

# 2. 安装根目录 HyperFrames 依赖
npm install

# 3. 安装前端依赖
cd framecraft-agent
npm install
cd ..

# 4. 安装后端依赖（自动创建 venv）
scripts\start-backend.bat
# 看到 Uvicorn running 后，新开一个终端继续

# 5. 启动前端（新终端）
scripts\start-frontend.bat

# 6. 浏览器打开
# http://127.0.0.1:5173/studio
```

**健康检查：**

- 前端：http://127.0.0.1:5173
- 后端：http://127.0.0.1:8000/api/health → `{"status":"ok"}`

---

## 详细安装

### 1. 克隆项目

```powershell
git clone https://github.com/Karl-XZ/FrameCraft-Agent.git
cd FrameCraft-Agent
```

### 2. 安装 Node.js（≥ 22.19）

```powershell
node --version   # 应 >= v22.19.0
npm --version
```

安装方式（任选其一）：

```powershell
# winget
winget install OpenJS.NodeJS

# 或 NVM for Windows
winget install CoreyButler.NVMforWindows
nvm install 22.21.1
nvm use 22.21.1
```

> **注意：** 若 Python 的 `Scripts` 目录下有同名 `node.exe`，会遮蔽真正的 Node。确保 Node 安装目录排在 PATH 前面。可用 `where.exe node` 验证。

### 3. 安装 Python 与 FFmpeg

```powershell
python --version   # 应 >= 3.10
ffmpeg -version
```

FFmpeg 可通过 winget、MSYS2 或 [ffmpeg.org](https://ffmpeg.org/download.html) 安装，并加入 PATH。

### 4. 安装 HyperFrames（项目根目录）

```powershell
cd FrameCraft-Agent
npm install
npx hyperframes --version   # 期望 0.6.99+
```

### 5. 安装前端依赖

```powershell
cd framecraft-agent
npm install
cd ..
```

### 6. 安装后端 Python 依赖

```powershell
python -m venv backend\venv
backend\venv\Scripts\activate
pip install -r backend\requirements.txt
```

### 7. 配置剪映路径

编辑 `config/local.paths.json`，填入本机剪映安装路径：

```json
{
  "jianying": {
    "app_exe": "F:\\JianyingPro\\JianyingPro.exe",
    "draft_dir": "C:\\Users\\你的用户名\\AppData\\Local\\JianyingPro\\User Data\\Projects\\com.lveditor.draft",
    "is_capcut_env": false
  }
}
```

**查找草稿目录：**

```text
剪映（中文）：%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft
CapCut 国际版：%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft
```

使用 CapCut 时将 `is_capcut_env` 改为 `true`。

### 8. 安装 VectCutAPI（剪映草稿导出）

仓库已包含 `vendor/VectCutAPI`。首次使用需创建虚拟环境：

```powershell
cd vendor\VectCutAPI
python -m venv venv-capcut
.\venv-capcut\Scripts\activate
pip install -r requirements.txt
cd ..\..
```

确认 `vendor/VectCutAPI/config.json` 存在，`is_capcut_env` 与所用软件一致。

### 9. 安装本地 ASR（推荐）

```powershell
python -m venv vendor\asr-venv
.\vendor\asr-venv\Scripts\activate
pip install faster-whisper
python -c "from faster_whisper import WhisperModel; print('OK')"
```

### 10. 预下载 Chromium（可选，加速首次渲染）

```powershell
npx --yes @puppeteer/browsers install chrome@stable
```

下载后位于项目 `chrome/` 目录，首次 HyperFrames 渲染会更快。

### 11. 环境自检

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-env.ps1
```

期望看到 Node、FFmpeg、Python、剪映路径、HyperFrames、VectCutAPI venv 等均为 `OK`。

---

## 配置说明

### 本机路径配置

文件：`config/local.paths.json`

| 字段 | 说明 |
|------|------|
| `jianying.app_exe` | 剪映程序路径 |
| `jianying.draft_dir` | 草稿导入目录 |
| `jianying.is_capcut_env` | `false`=剪映，`true`=CapCut |
| `tools.node_exe` | Node 可执行文件路径（多版本环境时指定） |

### 环境变量（可选）

```powershell
copy config\platform.env.example .env
```

| 变量 | 说明 |
|------|------|
| `JIANYING_DRAFT_DIR` | 剪映草稿目录 |
| `LLM_API_KEY` | OpenAI 兼容 API Key（启用 LLM 增强） |
| `LLM_MODEL` | 文本模型，默认 `gpt-4o` |
| `ASR_LOCAL_MODEL` | faster-whisper 模型，如 `base` |
| `UPLOADS_DIR` / `OUTPUTS_DIR` | 上传与输出目录 |

> `.env` 含敏感信息，**不要提交到 Git**。

### 模型设置（Web 界面）

启动后点击右上角 **「模型设置」**，可配置：

- LLM Provider 与 API Key
- VLM（视觉理解）模型
- ASR 模型

不填写 API Key 时，系统使用内置规则引擎完成基础剪辑，功能可跑通但智能化程度较低。

---

## 启动项目

需要 **两个终端**，分别启动后端和前端。

### 方式一：启动脚本（推荐）

**终端 1 — 后端（端口 8000）：**

```powershell
scripts\start-backend.bat
```

**终端 2 — 前端（端口 5173）：**

```powershell
scripts\start-frontend.bat
```

### 方式二：手动启动

**后端：**

```powershell
cd FrameCraft-Agent
backend\venv\Scripts\activate
pip install -r backend\requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**前端：**

```powershell
cd framecraft-agent
npm run dev
```

### 访问地址

| 页面 | 地址 |
|------|------|
| 落地页 | http://127.0.0.1:5173/ |
| **工作台** | http://127.0.0.1:5173/studio |
| API 文档 | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/api/health |

> **提示：** Vite 首次启动会进行依赖预构建，可能需要 1～2 分钟，之后启动会快很多。

### 生产构建（可选）

```powershell
cd framecraft-agent
npm run build
npm run preview   # 默认 http://127.0.0.1:4173
```

---

## 使用指南

### 完整工作流（5 步）

工作台顶部有进度条，对应以下步骤：

```text
① 上传素材 → ② AI 分析 → ③ 剪辑方案 → ④ 生成视频 → ⑤ 导出修改
```

#### 第 1 步：上传素材

1. 打开 http://127.0.0.1:5173/studio
2. 在左侧 **素材库** 拖拽或点击「选择文件」上传：
   - **口播视频**（必须）：主讲解视频
   - **B-roll**：产品界面、场景镜头等
   - **图片**：封面、产品图
   - **音频**：背景音乐 BGM
   - **Logo**：品牌标识
3. 上传时可填写 **标签** 和 **备注**，帮助 AI 理解素材用途

#### 第 2 步：AI 分析

1. 上传完成后，点击 **「开始 AI 分析」**
2. 系统自动执行：
   - 口播 ASR 转录（逐词时间戳）
   - 素材画面理解
   - 生成素材清单 `asset_manifest.json`
3. 页面通过 SSE 实时显示分析进度

#### 第 3 步：确认剪辑方案

分析完成后展示 **剪辑方案**，包括：

- Hook 开场设计
- 口播删减建议
- B-roll 匹配计划
- 字幕样式与动画
- 节奏与 BGM 建议

确认方案后点击 **「开始生成」**。

#### 第 4 步：生成视频

系统后台执行：

1. 构建 `unified_timeline.json`
2. HyperFrames 渲染预览视频（失败时 FFmpeg 兜底）
3. VectCutAPI 导出剪映草稿

生成完成后可在中间区域 **预览视频**，并查看版本信息。

#### 第 5 步：导出与修改

**下载：**

- **视频文件**：HyperFrames / FFmpeg 生成的 MP4 预览
- **草稿文件**：剪映草稿 ZIP，解压后导入剪映

**导入剪映：**

1. 下载草稿 ZIP 并解压，得到 `dfd_*` 文件夹
2. 复制到剪映草稿目录（见配置说明）
3. **重启剪映专业版**
4. 在草稿列表中打开，可继续精细编辑

**Agent 对话修改：**

在右侧 **Agent 对话** 面板用自然语言描述修改，例如：

- 「开头更有冲击力」
- 「字幕改成黄色大字」
- 「节奏加快」
- 「BGM 降低」
- 「第二段换成产品界面素材」

Agent 会将修改转为 timeline patch，自动重新生成新版本（v2、v3…）。

### 素材格式支持

| 类型 | 格式 |
|------|------|
| 视频 | MP4、MOV |
| 图片 | JPG、PNG |
| 音频 | MP3、WAV |

建议口播视频为竖屏 9:16（1080×1920），与短视频平台一致。

---

## 端到端测试

项目内置 API 级端到端测试脚本，无需浏览器：

```powershell
# 确保后端已启动
backend\venv\Scripts\activate
pip install httpx
python scripts\run_e2e_test.py
```

测试流程：

1. 健康检查
2. 用 FFmpeg 生成测试素材（口播、B-roll、图片、BGM）
3. 创建项目 → 上传 → 分析 → 生成 v1
4. Agent 对话修改 → 生成 v2
5. 输出报告到 `outputs/e2e_report.json`

---

## 项目结构

```text
FrameCraft-Agent/
├── README.md                      # 本文档
├── 准备工作.md                     # 详细环境搭建指南
├── 帧造_Agent_项目需求文档(2).md    # 完整需求规格
├── package.json                   # HyperFrames 根依赖
├── config/
│   ├── local.paths.json           # 本机路径（换机必改）
│   └── platform.env.example       # 环境变量模板
├── scripts/
│   ├── start-backend.bat          # 启动后端
│   ├── start-frontend.bat         # 启动前端
│   ├── verify-env.ps1             # 环境自检
│   └── run_e2e_test.py            # 端到端测试
├── backend/                       # FastAPI 后端
│   ├── app/
│   │   ├── main.py                # 入口
│   │   ├── routers/               # API 路由
│   │   ├── services/              # ASR、分析、渲染、草稿导出
│   │   └── models/                # 数据库模型
│   ├── requirements.txt
│   └── venv/                      # Python 虚拟环境（git 忽略）
├── framecraft-agent/              # React 前端
│   ├── src/
│   │   ├── api/client.ts          # API 客户端
│   │   ├── hooks/                 # 工作流 Hook
│   │   ├── components/            # UI 组件
│   │   └── store/                 # Zustand 状态
│   └── vite.config.ts             # 开发代理 /api → :8000
├── vendor/
│   ├── VectCutAPI/                # 剪映草稿 API
│   └── asr-venv/                  # faster-whisper 环境
├── uploads/                       # 用户上传（git 忽略）
├── outputs/                       # 生成产物（git 忽略）
└── workspaces/                    # 项目工作区（git 忽略）
```

### 主要 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/projects` | 创建项目 |
| POST | `/api/projects/{id}/assets/upload` | 上传素材 |
| POST | `/api/projects/{id}/assets/analyze` | 开始分析 |
| GET | `/api/projects/{id}/edit-plan` | 获取剪辑方案 |
| POST | `/api/projects/{id}/generate` | 开始生成 |
| GET | `/api/jobs/{id}/events` | SSE 任务进度 |
| GET | `/api/projects/{id}/versions` | 版本列表 |
| GET | `/api/projects/{id}/versions/{vid}/preview` | 下载预览视频 |
| GET | `/api/projects/{id}/versions/{vid}/draft` | 下载剪映草稿 |
| POST | `/api/projects/{id}/chat` | Agent 对话修改 |
| GET/PUT | `/api/settings/model` | 模型设置 |

完整 API 文档：http://127.0.0.1:8000/docs

---

## 常见问题

### Q1：`node --version` 报错或版本不对

Python `Scripts` 目录下的假 `node.exe` 可能遮蔽了真正的 Node。把 Node 安装目录放到 PATH 最前面：

```powershell
where.exe node
# 应指向 node-v22.x 或 Program Files\nodejs
```

### Q2：前端启动很慢或报 import 错误

- 首次 `npm run dev` 需 1～2 分钟做依赖预构建，属正常现象
- 若报 `Failed to resolve import`，执行 `cd framecraft-agent && npm install` 后重启

### Q3：剪映里看不到导入的草稿

1. 确认复制到 `com.lveditor.draft` 目录（不是上一级 `Projects`）
2. 文件夹名以 `dfd_` 开头
3. **重启剪映**
4. `config.json` 中 `is_capcut_env` 与软件版本一致

### Q4：HyperFrames 渲染失败或很慢

- 首次渲染需下载 Chromium，可提前执行 `npx @puppeteer/browsers install chrome@stable`
- 渲染失败时系统会用 FFmpeg 生成兜底预览，功能仍可继续
- 复杂 CSS 动效无法完全转为剪映原生元素，会烘焙为视频层

### Q5：没有 API Key 能用吗？

可以。无 LLM API Key 时走规则引擎，能完成上传、ASR、基础剪辑、生成和草稿导出。配置 Key 后分析质量和剪辑方案会明显提升。

### Q6：分析或生成任务失败

1. 查看后端终端日志
2. 确认 `vendor/asr-venv` 已安装 faster-whisper
3. 确认 FFmpeg 在 PATH 中：`ffmpeg -version`
4. 运行 `scripts\verify-env.ps1` 检查环境

### Q7：后端启动报模块找不到

```powershell
cd FrameCraft-Agent
backend\venv\Scripts\activate
pip install -r backend\requirements.txt
# 从项目根目录启动
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [`准备工作.md`](准备工作.md) | 完整环境搭建、剪映定位、各工具安装 |
| [`帧造_Agent_项目需求文档(2).md`](帧造_Agent_项目需求文档(2).md) | 产品需求与架构规格 |
| [`config/platform.env.example`](config/platform.env.example) | 环境变量参考 |

**外部链接：**

| 资源 | 链接 |
|------|------|
| HyperFrames | https://github.com/heygen-com/hyperframes |
| VectCutAPI | https://github.com/sun-guannan/VectCutAPI |
| OpenClaw | https://github.com/openclaw/openclaw |

---

## 许可证

本项目为比赛 / Demo 用途。第三方依赖（HyperFrames、VectCutAPI、OpenClaw 等）遵循各自的开源协议。

---

如有问题，欢迎在 [GitHub Issues](https://github.com/Karl-XZ/FrameCraft-Agent/issues) 反馈。
