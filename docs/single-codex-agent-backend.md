# 单一 Agent 后端说明

本文记录本次重做后的后端边界，方便以后继续改项目时不退回固定流水线。

## 目标

保留原前端交互，后端全部重做成最小编排层。每次用户发起任务，后端只启动或恢复一个项目 Agent，由这个 agent 从头到尾负责理解、设计、执行、验收和写回结果。

## 保留内容

- `framecraft-agent/` 前端保持原接口契约。
- 项目根 `package.json` 保留 HyperFrames 依赖。
- `uploads/` 和 `outputs/` 作为用户素材与版本输出目录继续使用。

## 删除内容

- 旧后端服务层。
- 固定 analyzer/planner/render pipeline。
- 旧多阶段 agent 调度。
- VectCutAPI 后端编排。
- 把失败伪装成成功的兜底逻辑。

## 新后端职责

`backend/app/main.py` 提供前端兼容 API：

- 项目创建、查询、删除。
- 素材上传、素材状态。
- 分析、生成、应用修改、对话任务启动。
- 每个项目的 active job 查询，供前端刷新后接回 SSE。
- Job 查询与 SSE 进度流。
- 版本列表和预览文件服务。
- 模型设置兼容接口。

`backend/app/single_agent.py` 负责：

- 每个任务生成一个 job。
- 首次任务启动一个持久项目 Agent 会话，并把真实 `thread_id` 保存到当前项目。
- 后续分析、生成、对话和改片任务优先恢复同一个项目 Agent 会话。
- 注入项目路径、任务参数和 `framecraft-tool.sh`。
- 将 Agent 事件、Agent `progress/log` 和失败说明同步写入项目聊天。
- 等待 Agent 返回。
- 执行产物后置校验。

`backend/app/agent_tool.py` 负责：

- 给 agent 提供 JSON 状态读写工具。
- 写分析文件、写剪辑方案、创建版本目录、注册版本、写聊天回复。
- `progress` 和 `log` 必须同时写入 job logs 与项目聊天，前端要能看到 Agent 的实时工作过程。
- 不做剪辑判断，不生成固定动画，不代替 agent 验收。

`backend/app/draft_exporter.py` 负责：

- 在 `register_version` 阶段读取当前版本的 `timeline.json`。
- 使用 vendored `VectCutAPI/pyJianYingDraft` 生成真实剪映草稿目录。
- 将主视频、字幕和可降级表达的信息图层写成可编辑轨道。
- 生成 `jianying_draft.zip`、`jianying_draft_manifest.json` 和 `jianying_import_guide.md`。
- 若项目设置 `generate_draft=true` 且草稿导出失败，注册版本失败，任务不得伪装为完成。

## 每个项目的 agent 边界

每个新建视频项目拥有一个独立 Agent 会话。首次任务完成 `thread.started` 后，后端保存真实 `thread_id`；同一项目后续生成、对话和修改必须恢复这个会话。这样生成系统和对话系统共享同一个项目级 Agent 上下文，不再是互相割裂的临时 agent。

“同一个 agent 从头到尾”同时包含两层含义：

- 单个 job 内只存在一个 Agent，不允许拆给多个子 agent 或固定流水线代判。
- 单个项目内尽量恢复同一个 Agent 会话，让后续聊天、改片和验收继承前面的项目语境。

如果历史项目没有有效 `thread_id`，下一次任务会创建新的项目会话并保存，之后继续复用。

每个项目拥有独立的 `agent_session_id`、素材目录、输出目录和聊天记录。`read_state` 只返回当前项目的状态、素材、版本和聊天历史，不返回其他项目内容。同一个项目同一时刻只允许一个运行中的 agent 任务，避免两个 agent 同时修改同一项目；不同项目可以各自启动独立任务。

## 安全边界

后端仍使用访问口令保护 API 入口。口令通过后，项目 Agent 使用本机完整权限运行，不再使用 `workspace-write` 限制，避免 ASR 模型下载、系统 Speech、浏览器渲染、字体和本地工具调用被内部沙盒阻断。Agent 仍必须避免读取、复制、扫描或删除与当前任务无关的个人文件，也不得主动读取其他 `proj_*` 的上传目录、输出目录、聊天记录或其他 job 工作目录。

Web API 默认启用访问口令，保护项目、素材、生成、聊天、下载和设置接口：

- `FRAMECRAFT_ACCESS_TOKEN` 存在时使用该环境变量。
- 未设置时自动生成 `backend/storage/access_token.txt`。
- 前端把口令放在 `X-FrameCraft-Token` 请求头中；视频、下载链接和 SSE 使用 `access_token` query 参数。
- `/api/health` 保持公开，方便探活。
- 可用 `FRAMECRAFT_DISABLE_AUTH=1` 临时关闭鉴权，但不要用于公网。
- CORS 默认允许 localhost 和常见局域网私有 IP；公网域名部署时应设置 `FRAMECRAFT_ALLOWED_ORIGINS`。

公开响应必须避免泄漏服务端内部信息：

- `public_project` 不返回 `agent_session_id`。
- `public_asset` 不返回本机 `path`。
- `public_version` 不返回 `version_dir`、`preview_path`、`draft_path`、`draft_dir`、`import_guide_path`。
- `/api/settings/model` 不返回或持久化浏览器提交的 `api_key`。

`agent_tool.py` 也必须做二次路径校验：

- `read_state` 只暴露当前项目的上传目录、输出目录和本项目聊天历史。
- `probe_media` 只能读取当前项目素材、输出、运行目录及项目内公开参考资料。
- `copy_file` 只能从允许目录复制到当前项目输出或当前 job 工作目录。
- `register_version` 只能注册当前项目输出目录内的版本。
- 如果路径越界，工具必须失败，不能静默兜底。

## 失败规则

后端不允许把 agent 失败伪装成成功：

- 本机 Agent 运行时不可用，任务不会启动。
- Agent 超时，任务失败。
- Agent 退出码非 0，任务失败。
- `analyze` 缺少 `analysis.json` 或 `edit_plan.json`，任务失败。
- `generate/apply_patch` 缺少 `preview.mp4`、`timeline.json`、`agent_visual_review.json` 或 HyperFrames 工程痕迹，任务失败。
- 项目开启 `generate_draft=true` 但缺少 `jianying_draft.zip`，任务失败。
- `chat` 没有写入 agent 回复，任务失败。

可由用户补充后继续的问题不得直接丢给红色失败状态。例如缺少可靠逐字稿、需要用户选择素材版本、用户需求互相冲突时，Agent 必须先在聊天里说明卡点、已尝试步骤和需要用户补充的内容，然后把 job/project 标记为 `needs_input`。前端把 `needs_input` 显示为“等待补充”，用户可以直接继续发消息让同一个项目 Agent 会话接着处理。

## 剪映草稿导出边界

剪映草稿不是从最终 MP4 反向还原，也不是空链接。当前实现从同一份统一时间线同步生成：

- 主讲视频轨：完整源视频，保留原音频。
- 字幕轨：逐段字幕，可在剪映中继续编辑。
- 信息图层：将 timeline blocks 转换为剪映可表达的文字卡片、淡入淡出和位移关键帧。

HyperFrames 预览仍是最终视觉效果的真实来源。CSS、GSAP、Lottie、Canvas 等复杂浏览器动画无法保证 100% 转成剪映原生可编辑动画；项目必须如实说明这一边界，不能把降级草稿说成完整反编译。

## 生成视频的 agent 要求

生成任务提示词要求 agent：

- 读取项目状态。
- 自行完成素材分析和 edit plan。
- 创建版本目录。
- 产出完整 `timeline.json`。
- 用 HyperFrames 真实渲染 `preview.mp4`。
- 抽关键帧或逐块截图做视觉复审。
- 如果构图、遮挡、字幕、动画密度或主观审美不过关，修改设计并重渲染。
- 通过后注册版本。

视频内容约束仍以 [Agent + HyperFrames 可复现口播制片工作流](codex-hyperframes-reproducible-workflow.md) 为准。

## 启动与验证

```bash
./scripts/setup-deps.sh
./scripts/verify-env.sh
./scripts/start-backend.sh
```

默认端口为后端 `8022`、前端 `5174`，并默认绑定 `0.0.0.0` 便于局域网访问。开发模式下 Vite 会把 `/api` 代理到 `http://127.0.0.1:8022`；如需改后端地址，设置：

```bash
FRAMECRAFT_BACKEND_URL=http://<host-ip>:8022 ./scripts/start-frontend.sh
```

基础烟测：

```bash
curl http://127.0.0.1:8022/api/health
```

对话链路烟测可以创建项目后调用 `POST /api/projects/{project_id}/chat`。如果 Agent 正常写回，job 会变成 `completed` 或 `needs_input`，聊天记录中会持续出现 role 为 `agent` 的状态、日志和最终回复。
