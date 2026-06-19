# Reaction Assets

本目录存放搞笑整活类视频可复现使用的轻量贴纸资产。

当前策略：

- 来源：OpenMoji 官方开源 SVG 图标。
- 目的：为 `funny_reaction` 类视频提供稳定、可复现、易渲染的现成贴纸，不依赖复杂骨骼动画模板。
- 使用方式：执行 `python3 scripts/bootstrap-reaction-assets.py` 下载项目内所需的最小子集。

已使用的上游资源：

- OpenMoji 官网：[https://openmoji.org/](https://openmoji.org/)
- OpenMoji GitHub：[https://github.com/hfg-gmuend/openmoji](https://github.com/hfg-gmuend/openmoji)

说明：

- 这些资产只用于视频中的装饰性表情贴纸，不替代字幕或核心信息卡。
- 若资产缺失，系统会自动回退为纯文本 emoji，不中断渲染。
