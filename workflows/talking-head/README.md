# 口播 HyperFrames 工作流（FrameCraft 内置）

三套已在 `C:\hf_demo` 跑通并 QA 的成片流程，供 **帧造 Agent** 在生成预览时自动选用。

## 工作流 ID

| ID | 画幅 | 何时自动选用 |
|----|------|----------------|
| `landscape_left` | 1920×1080 居左动效 + 右口播 | 项目 **16:9** 且源片为横屏 |
| `fullscreen_landscape` | 1920×1080 全屏 + 左右侧栏 | 项目 **16:9** 且源片为竖屏（需横裁） |
| `vertical_pip` | 1080×1920 裁切人物中上 + 下方动效 | 项目 **9:16**（默认） |

规则见 `registry.json`；实现见 `backend/app/services/talking_head_workflow_service.py`。

## 手动指定

生成任务 `job.meta.workflow_id` 设为上述 ID 之一可强制覆盖自动选择。

## 本地调试

```powershell
$env:FRAMECRAFT_WF_WORKSPACE = "D:\path\to\workspace"
$env:FRAMECRAFT_WF_INPUT = "$env:FRAMECRAFT_WF_WORKSPACE\input\talk.mp4"
$env:FRAMECRAFT_WF_DUR = "25.033"
python workflows/talking-head/scripts/build_vertical.py
```

## 文档

- [居左横版口播视频生成工作流.md](../../居左横版口播视频生成工作流.md)
- [全屏横版口播视频生成工作流.md](../../全屏横版口播视频生成工作流.md)
- [竖屏口播视频生成工作流.md](../../竖屏口播视频生成工作流.md)
