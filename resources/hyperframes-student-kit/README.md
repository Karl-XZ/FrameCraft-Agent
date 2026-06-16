# FrameCraft HyperFrames Student Kit（吸收自上游）

## 来源与协议（§8.5 / §26.2.1）

本组件库的视觉范式**吸收并改造**自社区项目
[`nateherkai/hyperframes-student-kit`](https://github.com/nateherkai/hyperframes-student-kit)：

- 固定参考版本：commit `a89e704ffbad02ac71170755526e05432598be59`
- 本地固定副本：`vendor/hyperframes-student-kit/`（不作为在线依赖，规避上游变动风险）
- 协议：上游代码与 composition 为 **MIT**；其 **AIS 品牌素材（logo/品牌规范）不可复用**，本项目已用通用配色与文案替换，不在产物中分发。
- 吸收对象：`video-projects/may-shorts-19`（9:16 口播 canonical）、`.claude/skills/short-form-video/SKILL.md`（playbook）、`compositions/captions.html`（逐词 karaoke 三态机）、`scene1-intro.html`（mono kicker + slam + stamp 擦入）。
- 吸收方式：**模板吸收 + 统一时间线驱动**（非黑盒运行）。具体技术与数值已改造进 `backend/app/services/hyperframes_service.py`：
  - karaoke 三态色彩机 `DIM → ACTIVE(放大1.14+强调色) → SPOKEN`，`back.out(3)` 缓动、分段淡入淡出；
  - Hook 面板 mono kicker + slam title + `clip-path:inset` stamp 擦入；
  - AIS-风格配色 token（`#07121C` / `#38BDF8` / `#96A2B6`）与 Montserrat/Roboto Mono 字体、底部 11.5% 字幕安全区、8 方向描边。

---

可复用的高级口播短视频组件库。`template_manifest.json` 定义了每个组件的：

- HyperFrames 预览实现方式（GSAP / CSS）
- 剪映草稿导出策略（`draft_export_mode`）
- 参数

后端 `backend/app/services/hyperframes_service.py` 据此生成预览，
`backend/app/services/draft_service.py` 据此导出剪映草稿。两端共享 `unified_timeline.json` 中
每个 item 的 `role` 与 `draft_export_mode`，保证「预览即所得 / 草稿可继续编辑」。

## 组件清单

| 组件 | role | 预览 | 草稿导出 |
|------|------|------|----------|
| Hook 大标题 | text/hook | GSAP 弹入 | native 文本 |
| 逐词高亮字幕 | subtitle | per-word GSAP color | native 字幕（可升级为 text_styles 逐词高亮）|
| Lower-third | text/lower_third | 左侧滑入 | native 文本 |
| 进度条 | shape/progress_bar | persistent-overlay | baked_overlay（省略）|
| B-roll 插入 | video/image | zoom_in + dissolve | native + 转场 |
| 画面推近 | video | GSAP scale | native 关键帧 |

## 渲染

```bash
npx hyperframes lint <project_dir>
npx hyperframes render <project_dir> -o preview.mp4 --fps 30 -q draft
```
