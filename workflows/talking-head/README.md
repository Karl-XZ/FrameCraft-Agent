# 口播 HyperFrames 参考工作流

本目录保留早期三套口播工作流，作为版式、安全区和 QA 的历史参考。当前生成流程以 Codex agent 写入 `hyperframes_design.json` 为准，不再把这里的流程当作固定模板自动套用。

## 工作流 ID

| ID | 画幅 | 可参考场景 |
|----|------|----------------|
| `landscape_left` | 1920×1080 居左动效 + 右口播 | 项目 **16:9** 且源片为横屏 |
| `fullscreen_landscape` | 1920×1080 全屏 + 左右侧栏 | 项目 **16:9** 且源片为竖屏（需横裁） |
| `vertical_pip` | 1080×1920 裁切人物中上 + 下方动效 | 项目 **9:16**（默认） |

规则见 `registry.json`；实现见 `backend/app/services/talking_head_workflow_service.py`。这些文件仅用于参考与兼容，不应替代 Codex 针对当前视频的设计规格。

## 手动指定

不建议在新任务中手动指定旧工作流。新任务应走 `build_timeline` → `write_hyperframes_design` → `build_hyperframes`。

## 本地调试

```powershell
$env:FRAMECRAFT_WF_WORKSPACE = "D:\path\to\workspace"
$env:FRAMECRAFT_WF_INPUT = "$env:FRAMECRAFT_WF_WORKSPACE\input\talk.mp4"
$env:FRAMECRAFT_WF_DUR = "25.033"
python workflows/talking-head/scripts/build_vertical.py
```

## 文档

- [Codex + HyperFrames 可复现口播制片工作流](../../docs/codex-hyperframes-reproducible-workflow.md)
- [居左横版口播视频生成工作流.md](../../居左横版口播视频生成工作流.md)
- [全屏横版口播视频生成工作流.md](../../全屏横版口播视频生成工作流.md)
- [竖屏口播视频生成工作流.md](../../竖屏口播视频生成工作流.md)
