# 单一 Codex Agent 后端说明

本文记录本次重做后的后端边界，方便以后继续改项目时不退回固定流水线。

## 目标

保留原前端交互，后端全部重做成最小编排层。每次用户发起任务，后端只启动一个 Codex CLI supervisor agent，由这个 agent 从头到尾负责理解、设计、执行、验收和写回结果。

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
- 启动一个 `codex exec --ephemeral` 进程。
- 注入项目路径、任务参数和 `framecraft-tool.sh`。
- 等待 Codex 返回。
- 执行产物后置校验。

`backend/app/agent_tool.py` 负责：

- 给 agent 提供 JSON 状态读写工具。
- 写分析文件、写剪辑方案、创建版本目录、注册版本、写聊天回复。
- 不做剪辑判断，不生成固定动画，不代替 agent 验收。

`backend/app/draft_exporter.py` 负责：

- 在 `register_version` 阶段读取当前版本的 `timeline.json`。
- 使用 vendored `VectCutAPI/pyJianYingDraft` 生成真实剪映草稿目录。
- 将主视频、字幕和可降级表达的信息图层写成可编辑轨道。
- 生成 `jianying_draft.zip`、`jianying_draft_manifest.json` 和 `jianying_import_guide.md`。
- 若项目设置 `generate_draft=true` 且草稿导出失败，注册版本失败，任务不得伪装为完成。

## 每次任务的 agent 边界

“同一个 agent 从头到尾”指一次 API 任务内只存在一个 Codex supervisor：

- 点击分析：一个 Codex agent 负责这次分析。
- 点击生成：一个 Codex agent 负责从读取素材到最终注册版本。
- 发送对话：一个 Codex agent 负责理解这条消息，必要时改片或回复。
- 应用修改：一个 Codex agent 负责读取 patch、重做、验收和注册新版本。

跨多次按钮点击不会强行复用同一个 CLI 进程，但所有历史状态、版本和聊天会写入项目存储，下一次任务会通过 `read_state` 读取上下文。

每个项目拥有独立的 `agent_session_id`、素材目录、输出目录和聊天记录。`read_state` 只返回当前项目的状态、素材、版本和聊天历史，不返回其他项目内容。同一个项目同一时刻只允许一个运行中的 agent 任务，避免两个 agent 同时修改同一项目；不同项目可以各自启动独立任务。

## 安全边界

后端启动 Codex 时不得使用 `--dangerously-bypass-approvals-and-sandbox`。默认使用 `workspace-write` 沙盒，并把可写范围限制在 FrameCraft 项目根目录内，防止 agent 轻易读取或删改用户电脑上的无关文件。Agent 提示词还必须明确禁止主动读取其他 `proj_*` 的上传目录、输出目录、聊天记录或其他 job 工作目录。

`agent_tool.py` 也必须做二次路径校验：

- `read_state` 只暴露当前项目的上传目录、输出目录和本项目聊天历史。
- `probe_media` 只能读取当前项目素材、输出、运行目录及项目内公开参考资料。
- `copy_file` 只能从允许目录复制到当前项目输出或当前 job 工作目录。
- `register_version` 只能注册当前项目输出目录内的版本。
- 如果路径越界，工具必须失败，不能静默兜底。

## 失败规则

后端不允许把 agent 失败伪装成成功：

- Codex CLI 不可用，任务不会启动。
- Codex 超时，任务失败。
- Codex 退出码非 0，任务失败。
- `analyze` 缺少 `analysis.json` 或 `edit_plan.json`，任务失败。
- `generate/apply_patch` 缺少 `preview.mp4`、`timeline.json`、`agent_visual_review.json` 或 HyperFrames 工程痕迹，任务失败。
- 项目开启 `generate_draft=true` 但缺少 `jianying_draft.zip`，任务失败。
- `chat` 没有写入 agent 回复，任务失败。

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

视频内容约束仍以 [Codex + HyperFrames 可复现口播制片工作流](codex-hyperframes-reproducible-workflow.md) 为准。

## 启动与验证

```bash
./scripts/setup-deps.sh
./scripts/verify-env.sh
./scripts/start-backend.sh
```

默认端口为后端 `8022`、前端 `5174`，并默认绑定 `0.0.0.0` 便于局域网访问。前端跨设备访问时必须设置：

```bash
VITE_API_BASE_URL=http://<host-ip>:8022 ./scripts/start-frontend.sh
```

基础烟测：

```bash
curl http://127.0.0.1:8022/api/health
```

对话链路烟测可以创建项目后调用 `POST /api/projects/{project_id}/chat`。如果 Codex agent 正常写回，job 会变成 `completed`，聊天记录中会出现 role 为 `agent` 的回复。
