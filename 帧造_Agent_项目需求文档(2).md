# 帧造 Agent 项目需求文档

> 英文名可辅助使用：**FrameCraft Agent**  
> 项目定位：AI 口播视频智能重构、HyperFrames 高级预览渲染、剪映 / CapCut 可编辑草稿同步生成平台。


---

## 0. 端到端完整系统定义

本项目必须被实现为一个完整的端到端视频重构系统，而不是单独的视频生成器、剪映插件或素材管理工具。开发时必须始终围绕以下主链路实现：

```text
用户上传口播和素材
        ↓
用户为每个素材添加主标签和备注
        ↓
系统自动理解口播内容、素材画面、素材备注与使用意图
        ↓
Agent 生成智能剪辑方案，包括删减口播、匹配 B-roll、设计字幕、动画、图文解释和节奏包装
        ↓
系统生成统一时间线 unified_timeline.json
        ↓
HyperFrames 根据统一时间线生成高级口播预览视频
        ↓
剪映 / CapCut Draft Exporter 根据同一份统一时间线同步生成可编辑草稿
        ↓
用户在 Web 页面预览视频、下载草稿，或继续和 Agent 对话修改
        ↓
修改请求转化为 timeline patch，并同步重新生成 HyperFrames 预览和剪映 / CapCut 草稿
```

因此，本项目的核心交付不是单个 MP4，也不是单个剪映草稿，而是：

1. 一个可上传和标注多素材的 Web 工作台；
2. 一个能读取用户备注并理解素材内容的多模态 Agent；
3. 一个能做口播智能剪辑决策的 Agent workflow；
4. 一份作为唯一事实来源的 `unified_timeline.json`；
5. 一个 HyperFrames 高级预览视频生成器；
6. 一个与预览同步的剪映 / CapCut 草稿导出器；
7. 一个支持后续对话修改并同步更新预览和草稿的 Web Agent 界面。

验收时必须证明该链路完整跑通：**上传素材 → 自动理解 → 智能剪辑 → HyperFrames 预览 → 剪映草稿同步 → 对话修改 → 双端重新生成**。

## 1. 项目概述

**帧造 Agent** 是一个可部署在服务器上的 Web 项目。用户上传一段或多段口播视频，以及多个辅助素材视频、图片、音频、截图、Logo 等素材，并可以为每个素材添加标签和备注。系统通过 Agent 理解素材本身内容与用户备注，自动生成高级口播短视频，并同步生成一个可导入剪映 / CapCut 继续修改的草稿工程。

项目核心不是“把 MP4 反编译成剪映工程”，而是以一份统一的结构化时间线 `unified_timeline.json` 为中心，同时导出：

1. HyperFrames HTML 工程；
2. HyperFrames 渲染出的预览视频；
3. 剪映 / CapCut 可编辑草稿；
4. 字幕文件、封面图、标题文案、发布文案等辅助内容。

本项目当前阶段以**比赛演示、Demo 验证、单平台体验**为主，前期**不设计多用户系统、登录注册、团队权限、用户隔离、计费系统**。所有访问者默认使用同一个平台工作区。后续如需商用，可再扩展为多用户 SaaS。

高级口播视频的视觉风格与模板体系不从零开始。项目需要优先参考并改造 HyperFrames 官方 skills，以及社区项目 `nateherkai/hyperframes-student-kit` 中的 `/short-form-video` playbook 和 `may-shorts-19` 等 9:16 talking-head 示例，用于实现动态字幕、motion graphics、karaoke captions、lower-third、短视频节奏包装等能力。

---

## 2. 项目目标

### 2.1 核心目标

用户上传口播视频和素材后，系统应自动完成：

1. 识别口播内容；
2. 自动转录并生成逐词级时间戳；
3. 删除明显停顿、废话、重复片段；
4. 自动生成字幕；
5. 根据口播内容和用户备注匹配素材；
6. 自动插入 B-roll、图片、产品截图、演示素材；
7. 自动生成高端口播包装效果，包括动态字幕、关键词高亮、标题卡片、图文解释、动画演示、转场、音效、BGM 等；
8. 使用 HyperFrames 渲染预览视频；
9. 同步生成剪映 / CapCut 可编辑草稿；
10. 用户可在 Web 界面中和 Agent 对话继续修改；
11. 修改后同步更新预览视频和剪映 / CapCut 草稿。

### 2.2 比赛展示目标

比赛 Demo 至少要能展示：

1. 上传口播视频与多个素材；
2. 为素材打标签和写备注；
3. Agent 自动理解口播和素材；
4. 自动生成高级口播视频；
5. 下载或预览 HyperFrames 渲染视频；
6. 下载剪映 / CapCut 草稿；
7. 打开剪映 / CapCut 草稿并证明字幕、视频片段、图片、音频等可以继续编辑；
8. 在 Web 中用自然语言要求修改；
9. 系统生成新版本视频和新版本草稿。

---

## 3. 当前阶段范围

### 3.1 当前版本采用单平台模式

当前阶段不做：

1. 用户注册；
2. 用户登录；
3. 多用户项目隔离；
4. 团队协作；
5. 用户权限管理；
6. 账号计费；
7. 用户级 API Key 管理；
8. 对外开放的公开 SaaS。

当前版本做：

1. 一个公共项目列表；
2. 一个公共素材存储区；
3. 一个公共模型配置入口；
4. 一个公共任务队列；
5. 一个演示用管理后台或配置页；
6. 所有项目默认对当前平台访问者可见。

### 3.2 后续可扩展多用户

虽然当前阶段不做多用户，但代码结构应尽量预留扩展空间。例如数据库表可以暂时不含 `user_id`，但项目目录结构和 API 设计不要阻碍后续增加用户系统。

---

## 4. 非目标与边界说明

### 4.1 不做 MP4 到剪映工程的反向还原

系统不承诺把 HyperFrames 渲染出的 MP4 自动反向还原成可编辑剪映工程。

正确流程是：

```text
用户素材 + 用户备注
        ↓
素材理解 + 口播分析
        ↓
Agent 生成剪辑方案
        ↓
unified_timeline.json
        ↓
├── HyperFrames HTML 工程
├── HyperFrames 预览视频
└── 剪映 / CapCut 草稿
```

### 4.2 不承诺所有高级动画在剪映中 100% 原生可编辑

HyperFrames 支持 HTML、CSS、GSAP、Lottie、Three.js、Canvas 等复杂效果，而剪映 / CapCut 草稿格式无法完全表达这些浏览器能力。

系统应承诺：

1. 视频片段、图片、音频、字幕、普通标题、基础文本尽量原生可编辑；
2. 简单位置、缩放、旋转、透明度动画尽量转换为剪映关键帧；
3. 复杂 CSS / GSAP / Lottie / Three.js 动效可以烘焙为视频层、透明视频层或覆盖层；
4. 剪映草稿应与 HyperFrames 预览视频视觉高度一致，但不保证所有元素原生可编辑。

### 4.3 不依赖官方剪映开放 API

当前公开环境中没有可直接调用的官方剪映完整剪辑 API。因此系统通过草稿生成工具实现工程导出，例如：

1. VectCutAPI / CapCutAPI；
2. capcut-cli；
3. jianying-mcp；
4. jianying-protocol-service；
5. pyJianYingDraft 或其他可写入草稿的库。

项目应实现统一 Draft Exporter 抽象层，避免强绑定单一实现。

---

## 5. 核心使用流程

### 5.1 新建项目

用户在首页点击“新建项目”，填写：

1. 项目名称；
2. 视频比例：默认 9:16，可选 16:9、1:1；
3. 目标时长：默认 30–90 秒；
4. 视频风格：高级口播、产品介绍、知识科普、比赛路演、探店种草、课程讲解、Vlog 解说等；
5. 输出语言：中文、英文、双语；
6. 是否生成剪映 / CapCut 草稿；
7. 是否保留 HyperFrames 源工程。

### 5.2 上传素材

用户上传：

1. 口播视频；
2. 其他素材视频；
3. 图片；
4. 截图；
5. Logo；
6. 背景音乐；
7. 音效；
8. 其他补充素材。

每个素材需要支持：

1. 主标签；
2. 用户备注；
3. 是否必须使用；
4. 推荐对应口播段落；
5. 是否静音；
6. 是否裁剪；
7. 优先级。

### 5.3 自动分析素材

系统自动：

1. 提取视频元信息；
2. 提取口播音频；
3. 对口播做 ASR 转录；
4. 获取逐词时间戳；
5. 分句、分段；
6. 检测停顿、重复和废话；
7. 对其他视频抽帧理解；
8. 对图片做视觉理解和 OCR；
9. 结合用户备注生成素材清单 `asset_manifest.json`。

### 5.4 Agent 生成剪辑方案

Agent 根据口播内容、素材清单、用户备注和目标风格生成剪辑方案，包括：

1. 视频结构；
2. 开头 Hook；
3. 保留和删除的口播片段；
4. B-roll 插入位置；
5. 字幕样式；
6. 关键词高亮；
7. 图文解释动画；
8. 标题卡片；
9. 转场；
10. BGM 和音效；
11. 封面标题；
12. 发布文案。

### 5.5 生成统一时间线

系统把剪辑方案转换为 `unified_timeline.json`。该文件是整个项目的唯一事实来源。

### 5.6 渲染预览视频

系统把 `unified_timeline.json` 转换成 HyperFrames HTML 工程，然后调用 HyperFrames 渲染出 `preview.mp4`。

### 5.7 导出剪映 / CapCut 草稿

系统把同一份 `unified_timeline.json` 转换为剪映 / CapCut 草稿，并生成可下载 zip 包。

### 5.8 对话修改

用户在 Web 中输入修改要求，例如：

1. “开头更炸一点”；
2. “第二段换成我上传的产品界面素材”；
3. “字幕改成黄色大字”；
4. “BGM 小一点”；
5. “整体节奏再快一点”；
6. “第 15 秒加一个价格对比动画”。

Agent 生成 timeline patch，系统应用 patch 后重新导出预览视频和剪映 / CapCut 草稿。

---

## 6. 功能需求

## 6.1 项目管理

当前阶段项目不绑定用户，所有项目位于公共项目列表中。

项目字段：

```text
id
name
status
aspect_ratio
target_style
target_duration
current_version_id
created_at
updated_at
```

项目状态：

```text
created
uploading
analyzing
planning
rendering
exporting_draft
completed
failed
cancelled
```

## 6.2 素材上传模块

### 6.2.1 支持格式

视频：

```text
mp4, mov, webm, mkv
```

图片：

```text
png, jpg, jpeg, webp
```

音频：

```text
mp3, wav, m4a, aac
```

### 6.2.2 MVP 文件限制

建议限制：

1. 单个视频最大 1GB；
2. 单个图片最大 50MB；
3. 单个项目最多 30 个素材；
4. 单个项目总大小最多 3GB；
5. 口播视频最大时长 30 分钟；
6. 输出视频建议 15 秒到 3 分钟。

### 6.2.3 上传交互

需要支持：

1. 拖拽上传；
2. 多文件上传；
3. 上传进度显示；
4. 上传失败重试；
5. 上传完成生成缩略图；
6. 素材标签和备注编辑。

## 6.3 素材理解模块

### 6.3.1 口播视频分析

需要输出：

1. `transcript.json`：完整转录文本；
2. `word_timestamps.json`：逐词时间戳；
3. `speech_segments.json`：口播分段；
4. `cut_candidates.json`：建议删除的停顿、重复和废话；
5. `highlight_sentences.json`：重点句和 Hook 候选句。

### 6.3.2 其他视频素材分析

需要完成：

1. 获取时长、分辨率、帧率；
2. 每 1–3 秒抽关键帧；
3. 生成画面描述；
4. 识别场景、人物、物体、界面、文字；
5. 判断是否适合做 B-roll；
6. 结合用户备注推荐插入位置。

### 6.3.3 图片素材分析

需要完成：

1. 图片描述；
2. OCR；
3. 判断用途：封面、插图、Logo、解释卡片、背景图、产品图等；
4. 推荐使用位置。

### 6.3.4 素材清单结构

输出 `asset_manifest.json`：

```json
{
  "project_id": "project_001",
  "assets": [
    {
      "asset_id": "asset_001",
      "file_path": "uploads/project_001/talking_head.mp4",
      "type": "video",
      "user_label": "口播视频",
      "user_note": "这是第一段口播",
      "must_use": true,
      "duration": 128.4,
      "resolution": [1920, 1080],
      "auto_summary": "用户正在介绍一个 AI 剪辑产品",
      "recommended_usage": ["main_speech_track"]
    }
  ]
}
```

## 6.4 Agent 剪辑规划模块

### 6.4.1 Agent 输入

Agent 输入包括：

1. 项目目标；
2. 视频风格；
3. 所有素材备注；
4. 所有素材自动理解结果；
5. 口播 transcript；
6. 口播时间戳；
7. 目标时长；
8. 可用视觉模板；
9. 剪映草稿导出能力边界；
10. 目标平台，例如抖音、TikTok、B站、小红书。

### 6.4.2 Agent 输出

Agent 输出结构化剪辑方案 `edit_plan.json`：

```json
{
  "video_concept": "高级 AI 产品介绍口播短视频",
  "target_duration": 60,
  "style": "modern_talking_head",
  "scenes": [
    {
      "scene_id": "scene_001",
      "purpose": "hook",
      "timeline_start": 0,
      "timeline_end": 5,
      "speech_source": {
        "asset_id": "asset_talk_001",
        "source_start": 10.2,
        "source_end": 15.2
      },
      "caption": "普通人也能一键剪出高级口播视频",
      "visual_effects": ["big_hook_title", "word_highlight"],
      "broll": []
    }
  ]
}
```

### 6.4.3 口播智能剪辑规则

系统需要支持：

1. 删除长停顿；
2. 删除明显重复句；
3. 删除无意义语气词；
4. 保留语义完整性；
5. 不破坏人声自然节奏；
6. 根据目标时长压缩内容；
7. 优先保留 Hook、核心观点、案例、结论；
8. 支持“尽量完整保留口播”和“节奏尽量快”两种策略。

### 6.4.4 B-roll 匹配规则

匹配优先级：

1. 用户明确备注对应段落；
2. 用户标记必须使用；
3. 自动视觉理解与口播语义匹配；
4. 素材质量；
5. 视频风格匹配；
6. 未使用素材优先补充。

## 6.5 高级口播视觉能力

系统至少支持以下效果：

1. 开头 Hook 大标题；
2. 动态字幕；
3. 关键词高亮；
4. 关键词弹出；
5. Lower-third 信息条；
6. 章节标题卡；
7. 图文解释卡片；
8. 价格 / 步骤 / 流程 / 对比动画；
9. 手绘圈选、箭头、标注；
10. B-roll 插入；
11. 局部放大；
12. 背景渐变或动效；
13. 转场；
14. 音效；
15. 结尾 CTA。

---

## 7. 统一时间线设计

## 7.1 核心原则

`unified_timeline.json` 是核心数据结构。所有输出都由它导出：

```text
unified_timeline.json
├── HyperFrames HTML
├── preview.mp4
├── CapCut / Jianying draft
├── subtitles.srt
├── cover.png
└── publish_copy.json
```

任何用户修改都必须先变成 timeline patch，再重新导出。

## 7.2 基本结构

```json
{
  "version": "1.0",
  "project": {
    "id": "project_001",
    "name": "帧造 Agent Demo",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "duration": 60,
    "background": "#000000"
  },
  "assets": [],
  "tracks": [],
  "scenes": [],
  "styles": {},
  "export_settings": {}
}
```

## 7.3 Track 类型

```text
video
audio
image
text
subtitle
shape
effect
overlay_rendered
```

## 7.4 Item 类型

```json
{
  "id": "item_001",
  "type": "video",
  "asset_id": "asset_001",
  "track_id": "track_video_001",
  "timeline_start": 0,
  "timeline_end": 5,
  "source_start": 10,
  "source_end": 15,
  "transform": {
    "x": 0,
    "y": 0,
    "scale": 1,
    "rotation": 0,
    "opacity": 1
  },
  "animations": [],
  "editable_in_draft": true,
  "draft_export_mode": "native"
}
```

## 7.5 剪映可编辑性标记

每个元素都需要标记导出方式：

```text
native：剪映 / CapCut 原生可编辑
baked_overlay：渲染为覆盖层
baked_video：渲染为视频层
unsupported：暂不导出
```

---

## 8. HyperFrames 导出模块

## 8.1 功能

将 `unified_timeline.json` 转换为 HyperFrames HTML 工程，支持：

1. 视频轨道；
2. 图片轨道；
3. 音频轨道；
4. 字幕轨道；
5. 文本轨道；
6. CSS 动画；
7. GSAP 动画；
8. Lottie；
9. Three.js，可选；
10. MP4 预览渲染。

## 8.2 Worker 环境要求

```text
Node.js 22+
FFmpeg
Chromium / Chrome
HyperFrames CLI
Noto Sans CJK 字体
Emoji 字体
```

## 8.3 输出目录

```text
outputs/{project_id}/{version}/preview.mp4
outputs/{project_id}/{version}/hyperframes/index.html
outputs/{project_id}/{version}/hyperframes/assets/
outputs/{project_id}/{version}/render_log.json
```

## 8.4 渲染要求

1. 默认输出 1080x1920；
2. 默认 30fps；
3. 支持 720p 快速预览；
4. 支持 1080p 正式导出；
5. 支持渲染失败重试；
6. 支持进度回传。

## 8.5 HyperFrames Student Kit 接入要求

项目需要将社区项目 `nateherkai/hyperframes-student-kit` 作为高级口播视频模板和制作范式的重要参考。该项目不应被视为“完整智能剪辑系统”，而应作为 HyperFrames 高级短视频工程的模板库、playbook 和视觉参考。

### 8.5.1 参考仓库

```text
https://github.com/nateherkai/hyperframes-student-kit
```

### 8.5.2 重点参考内容

MVP 优先参考以下内容：

1. `.claude/skills/short-form-video`：短视频口播制作 playbook；
2. `video-projects/may-shorts-19`：9:16 TikTok-style talking-head、motion graphics、karaoke captions 的重点参考；
3. `video-projects/may-shorts-18`：同系列早期版本，可用于对比短视频模板迭代；
4. `video-projects/may-shorts-6`：16:9 talking-head 参考，可用于横屏版本扩展；
5. 其他 product promo / sizzle reel 示例：作为产品演示、官网转视频、营销短片模板参考。

### 8.5.3 接入方式

推荐采用“模板吸收 + 统一时间线驱动”的方式，而不是直接把 Student Kit 作为黑盒运行。

建议目录结构：

```text
resources/hyperframes-student-kit/
  README.md
  templates/
    short_form_vertical/
    talking_head_karaoke/
    lower_third/
    hook_title/
    follow_overlay/
  template_manifest.json
```

具体要求：

1. 固定参考仓库版本或 commit，避免模板随上游变化导致渲染结果不稳定；
2. 提取可复用视觉组件，例如 karaoke captions、hook title、lower-third、progress bar、follow overlay、caption emphasis、motion graphics blocks；
3. 为每个模板建立 `template_manifest.json`，描述支持的输入、输出、可编辑性、剪映草稿导出策略；
4. HyperFrames Exporter 根据 `unified_timeline.json` 和模板 ID 生成对应 HTML 工程；
5. Agent 剪辑规划模块可以读取模板能力清单，避免生成模板不支持的效果；
6. 对来源模板保留许可证、来源链接和修改说明。

### 8.5.4 与剪映草稿同步的处理

Student Kit 中的部分高级效果可能无法在剪映 / CapCut 中原生编辑。因此每个从 Student Kit 提取的视觉组件都必须声明导出策略：

```text
native_text：转为剪映原生文本或字幕
native_media：转为剪映原生视频 / 图片 / 音频
native_keyframe：转为剪映基础关键帧
baked_overlay：渲染为透明覆盖层
baked_video：渲染为普通视频层
hyperframes_only：仅在 HyperFrames 预览中出现，草稿中降级或忽略
```

MVP 中，karaoke captions、普通标题、lower-third 的文字内容应尽量导出为剪映原生可编辑文本；复杂 motion graphics、粒子、shader、复杂 CSS 动效允许烘焙为覆盖层。

### 8.5.5 对帧造 Agent 的定位

Student Kit 负责提供“高级口播视频长什么样”的模板和制作范式；帧造 Agent 负责补足它没有覆盖的产品能力：

1. 用户上传真实素材；
2. 读取用户对每个素材的备注；
3. 自动理解口播和 B-roll 内容；
4. 判断哪些口播应该保留、删除、重排；
5. 自动匹配素材到口播段落；
6. 生成 `unified_timeline.json`；
7. 同步导出 HyperFrames 高级预览与剪映 / CapCut 可编辑草稿；
8. 支持 Web 对话修改并同步更新两种输出。

---

## 9. 剪映 / CapCut 草稿导出模块

## 9.1 功能

将 `unified_timeline.json` 转换为剪映 / CapCut 可编辑草稿。

## 9.2 Draft Exporter 抽象接口

```ts
interface DraftExporter {
  name: string;
  supportedTargets: string[];
  exportDraft(input: UnifiedTimeline, options: DraftExportOptions): Promise<DraftExportResult>;
  validateDraft(path: string): Promise<ValidationResult>;
}
```

## 9.3 支持目标

MVP 阶段至少支持一种：

```text
CapCut International draft
Jianying compatible draft
```

建议优先支持 CapCut International，因为版本兼容风险相对更低。中文剪映需要明确推荐版本。

## 9.4 草稿内容

草稿至少应包含：

1. 主口播视频片段；
2. B-roll 视频片段；
3. 图片素材；
4. 字幕文本；
5. 标题文本；
6. 音频；
7. 基础转场；
8. 基础动画；
9. 简单关键帧；
10. 渲染覆盖层。

## 9.5 导出策略

| 元素类型 | 导出策略 |
|---|---|
| 视频 | 原生视频片段 |
| 图片 | 原生图片片段 |
| 普通字幕 | 原生文本 / 字幕 |
| 标题 | 原生文本 |
| BGM | 原生音频 |
| 音效 | 原生音频 |
| 简单缩放 / 移动 | 尽量转关键帧 |
| 复杂 CSS 动效 | 渲染为 overlay |
| Lottie | 优先转视频 / 透明层 |
| Three.js | 渲染为视频层 |
| 复杂图文动画 | 可拆则拆，不可拆则烘焙 |

## 9.6 输出文件

```text
outputs/{project_id}/{version}/draft/
outputs/{project_id}/{version}/draft.zip
outputs/{project_id}/{version}/draft_import_guide.md
```

## 9.7 兼容性提示

导出完成后，前端需要显示：

1. 推荐剪映 / CapCut 版本；
2. 如何导入草稿；
3. 哪些元素可编辑；
4. 哪些元素是渲染覆盖层；
5. 可能存在的版本兼容风险。

---

## 10. 对话修改模块

## 10.1 功能

用户可以通过自然语言修改视频。需要支持：

1. 修改字幕内容；
2. 修改字幕样式；
3. 替换素材；
4. 调整 B-roll；
5. 删除片段；
6. 增加片段；
7. 调整节奏；
8. 调整 BGM 音量；
9. 修改标题；
10. 修改封面文案；
11. 修改视频风格；
12. 重新生成某一段。

## 10.2 修改流程

```text
用户消息
  ↓
Agent 理解意图
  ↓
生成 timeline patch
  ↓
系统验证 patch
  ↓
应用 patch
  ↓
生成新 timeline version
  ↓
重新生成 HyperFrames 工程
  ↓
重新渲染 preview.mp4
  ↓
重新导出剪映 / CapCut 草稿
```

## 10.3 Patch 格式

```json
{
  "patch_id": "patch_001",
  "description": "把开头字幕改得更夸张",
  "operations": [
    {
      "op": "update_item",
      "target_id": "subtitle_001",
      "changes": {
        "text": "普通人也能一键剪出高级大片！",
        "style": "hook_bold_yellow"
      }
    }
  ]
}
```

## 10.4 Patch 验证

系统需要验证：

1. 时间线不能出现异常重叠；
2. 资源必须存在；
3. 片段不能超出源素材时长；
4. 字幕不能为空；
5. 输出总时长合理；
6. 不能引用未上传素材；
7. 不能删除所有主口播轨道。

---

## 11. 前端界面需求

## 11.1 总体风格

前端需要精美、现代、适合比赛演示。建议：

1. 深色主题；
2. 科技感渐变背景；
3. 卡片式布局；
4. 玻璃拟态；
5. 清晰的上传区；
6. Agent 聊天侧边栏；
7. 视频预览居中；
8. 简化时间线位于底部；
9. 输出结果明确。

## 11.2 页面结构

当前单平台版本需要：

1. 首页 / 产品介绍页；
2. 项目列表页；
3. 新建项目页；
4. 素材上传与标注页；
5. 分析进度页；
6. 剪辑方案确认页；
7. 视频预览与对话修改页；
8. 导出结果页；
9. 平台设置页。

不需要登录页和用户中心。

## 11.3 预览与修改页布局

建议布局：

```text
左侧：素材库与剪辑结构
中间：视频预览播放器
右侧：Agent 对话框
底部：简化时间线
```

需要支持：

1. 播放预览视频；
2. 查看当前剪辑结构；
3. 查看字幕；
4. 发送修改指令；
5. 查看 Agent 修改计划；
6. 接受或撤销修改；
7. 下载 MP4；
8. 下载剪映 / CapCut 草稿；
9. 查看导入说明。

## 11.4 任务进度显示

通过 SSE 或 WebSocket 显示：

1. 上传进度；
2. 转录进度；
3. 素材理解进度；
4. Agent 规划进度；
5. HyperFrames 生成进度；
6. 渲染进度；
7. 草稿导出进度；
8. 错误信息。

---

## 12. 模型与 OpenClaw 要求

## 12.1 OpenClaw 定位

OpenClaw 在本项目中作为 Agent 编排层，用于：

1. 调用不同模型；
2. 根据素材和用户需求生成剪辑方案；
3. 生成 HyperFrames 代码或配置；
4. 生成 timeline patch；
5. 调用受控工具执行任务；
6. 允许平台切换模型配置。

## 12.2 模型配置

当前单平台版本采用**平台级模型配置**，不是用户级配置。

平台设置页可配置：

1. Provider；
2. API Key；
3. 默认文本模型；
4. 默认视觉模型；
5. 默认 ASR 模型；
6. 是否启用本地模型。

API Key 可保存在 `.env` 或后端配置文件中。比赛演示阶段也可以直接在平台设置页临时填写，但不得写入公开日志。

## 12.3 支持模型类型

至少支持：

1. 文本 LLM：剪辑规划、对话修改；
2. 视觉语言模型：图片 / 视频帧理解；
3. ASR 模型：口播转录；
4. 可选 TTS 模型：生成旁白；
5. 可选 Embedding 模型：素材与口播语义匹配。

## 12.4 Agent 工具白名单

OpenClaw 执行环境只允许访问：

1. 当前项目素材目录；
2. 当前项目输出目录；
3. HyperFrames；
4. FFmpeg；
5. ASR 工具；
6. VLM 工具；
7. Draft Exporter；
8. unified timeline 文件；
9. 日志文件。

禁止：

1. 访问服务器敏感路径；
2. 删除系统文件；
3. 输出 API Key；
4. 修改全局系统配置；
5. 执行高风险 shell 命令。

---

## 13. 系统架构

## 13.1 推荐架构

```text
Frontend: Next.js / React / Tailwind / shadcn-ui
        ↓
Backend API: FastAPI 或 Node.js / NestJS
        ↓
Database: SQLite 或 PostgreSQL
        ↓
Queue: Redis + Celery / BullMQ
        ↓
Worker Container:
  - OpenClaw runtime
  - Node.js 22+
  - HyperFrames
  - Chromium
  - FFmpeg
  - Python media tools
  - ASR / VLM adapters
  - Draft Exporters
        ↓
Storage: 本地文件系统 / MinIO / S3 / R2
```

## 13.2 MVP 简化架构

为了比赛演示，MVP 可以采用：

```text
Next.js 前端 + FastAPI 后端
SQLite 数据库
本地 uploads/outputs 文件夹
单 Worker 进程
Redis 可选
```

只要任务流程稳定，后续再拆成多容器架构。

## 13.3 主要服务

### Frontend

负责：

1. 项目列表；
2. 新建项目；
3. 上传素材；
4. 标注备注；
5. 视频预览；
6. Agent 对话；
7. 下载结果。

### Backend API

负责：

1. 项目 CRUD；
2. 素材 metadata；
3. 任务提交；
4. 任务状态查询；
5. 对话消息；
6. 模型配置；
7. 输出文件下载。

### Worker

负责：

1. 媒体分析；
2. Agent 规划；
3. HyperFrames 工程生成；
4. 视频渲染；
5. 剪映草稿导出；
6. 对话修改；
7. 日志输出。

---

## 14. 数据库设计

## 14.1 projects

```text
id
name
status
aspect_ratio
target_style
target_duration
current_version_id
created_at
updated_at
```

## 14.2 assets

```text
id
project_id
file_name
file_path
file_type
mime_type
size
duration
width
height
user_label
user_note
must_use
priority
analysis_status
analysis_json_path
created_at
updated_at
```

## 14.3 project_versions

```text
id
project_id
version_number
timeline_json_path
preview_video_path
hyperframes_path
draft_zip_path
status
created_at
```

## 14.4 jobs

```text
id
project_id
type
status
progress
current_step
error_message
log_path
created_at
started_at
completed_at
```

## 14.5 chat_messages

```text
id
project_id
version_id
role
content
patch_json_path
created_at
```

## 14.6 platform_settings

```text
id
key
value_encrypted_or_plain
created_at
updated_at
```

用于保存平台级模型 Provider、默认模型、API Key 等配置。比赛 Demo 也可以直接用 `.env`，该表可选。

---

## 15. API 设计

## 15.1 项目 API

```text
POST /api/projects
GET /api/projects
GET /api/projects/{project_id}
PATCH /api/projects/{project_id}
DELETE /api/projects/{project_id}
```

## 15.2 素材 API

```text
POST /api/projects/{project_id}/assets/upload
GET /api/projects/{project_id}/assets
PATCH /api/assets/{asset_id}
DELETE /api/assets/{asset_id}
POST /api/projects/{project_id}/assets/analyze
```

## 15.3 生成 API

```text
POST /api/projects/{project_id}/generate
GET /api/jobs/{job_id}
GET /api/jobs/{job_id}/events
POST /api/jobs/{job_id}/cancel
```

## 15.4 对话修改 API

```text
POST /api/projects/{project_id}/chat
GET /api/projects/{project_id}/chat
POST /api/projects/{project_id}/apply-patch
POST /api/projects/{project_id}/regenerate
```

## 15.5 导出 API

```text
GET /api/projects/{project_id}/versions/{version_id}/preview
GET /api/projects/{project_id}/versions/{version_id}/draft
GET /api/projects/{project_id}/versions/{version_id}/hyperframes
GET /api/projects/{project_id}/versions/{version_id}/timeline
```

## 15.6 平台模型设置 API

```text
GET /api/settings/model
PATCH /api/settings/model
GET /api/model-providers
```

---

## 16. 任务流程

## 16.1 初次生成任务

```text
1. 验证项目和素材
2. 创建 job
3. 提取口播音频
4. ASR 转录
5. 分析口播
6. 抽帧分析 B-roll 和图片
7. 生成 asset_manifest
8. Agent 生成 edit_plan
9. 转换为 unified_timeline
10. 生成 HyperFrames 工程
11. 渲染 preview.mp4
12. 导出剪映 / CapCut 草稿
13. 保存 project_version
14. 通知前端完成
```

## 16.2 对话修改任务

```text
1. 读取当前 timeline
2. 读取用户消息
3. Agent 生成 patch
4. 验证 patch
5. 应用 patch 生成新 timeline
6. 重新生成 HyperFrames 工程
7. 重新渲染 preview.mp4
8. 重新导出剪映 / CapCut 草稿
9. 保存新版本
10. 通知前端完成
```

---

## 17. 内置高级口播模板

## 17.0 模板来源与复用策略

内置模板不从零设计，优先复用和改造以下来源：

1. HyperFrames 官方 skills：用于基础 composition、CLI 渲染、media 转录、字幕、GSAP / CSS / Lottie / Three.js 动效；
2. `nateherkai/hyperframes-student-kit`：用于高级短视频视觉范式，尤其是 `/short-form-video` playbook 和 `may-shorts-19`；
3. 项目自定义模板：将上述能力封装为适合“帧造 Agent”的模板，例如高级口播、产品介绍、知识讲解、比赛路演等。

每个模板都需要包含：

1. 模板名称；
2. 适用场景；
3. 支持的视频比例；
4. 输入要求；
5. 必需素材；
6. 可选素材；
7. HyperFrames 效果；
8. 剪映 / CapCut 导出策略；
9. 是否支持原生可编辑；
10. 是否需要烘焙覆盖层。

## 17.1 Modern Talking Head

特点：

1. 大号动态字幕；
2. 关键词高亮；
3. B-roll 自动插入；
4. 顶部进度条；
5. 开头 Hook；
6. 章节卡片；
7. 结尾 CTA。

## 17.2 Product Demo

特点：

1. 口播 + 产品界面录屏；
2. 局部放大；
3. 箭头标注；
4. 功能步骤卡；
5. 价格 / 效果对比；
6. Logo 与品牌色。

## 17.3 Educational Explainer

特点：

1. 分步骤讲解；
2. 关键词定义卡；
3. 简单图形动画；
4. 流程图；
5. 总结卡片。

## 17.4 Viral Short

特点：

1. 开头强 Hook；
2. 快节奏剪辑；
3. 大字幕；
4. 音效；
5. 强对比文案；
6. 结尾互动提问。

## 17.5 Student Kit Short Form Vertical

该模板是 MVP 最重要的高级口播参考模板，基于 `nateherkai/hyperframes-student-kit` 中 `/short-form-video` 和 `may-shorts-19` 的制作范式改造。

特点：

1. 9:16 竖屏口播短视频；
2. TikTok / 抖音风格 talking-head 布局；
3. Karaoke captions / 逐词动态字幕；
4. 关键词强调和弹跳动画；
5. 片头强 Hook 大标题；
6. lower-third 信息条；
7. motion graphics 辅助解释；
8. B-roll 和口播画面智能切换；
9. 适合产品介绍、观点表达、课程切片、比赛路演压缩版；
10. 复杂动效允许烘焙为 overlay，但字幕和核心文字尽量导出为剪映原生文本。

MVP 中，系统应至少能用该模板完成一个“上传口播 + B-roll + 备注 → 自动生成高级竖屏口播视频 + 剪映草稿”的完整演示。

---

## 18. 输出内容

每个完成版本输出：

1. `preview.mp4`：预览视频；
2. `draft.zip`：剪映 / CapCut 草稿；
3. `hyperframes_project.zip`：HyperFrames 工程；
4. `subtitles.srt`：字幕文件；
5. `unified_timeline.json`：统一时间线；
6. `cover.png`：封面图；
7. `publish_copy.json`：发布标题、文案、话题标签；
8. `draft_import_guide.md`：草稿导入说明。

---

## 19. 性能要求

MVP 目标：

1. 5 分钟口播视频分析时间不超过 5 分钟；
2. 60 秒成片 720p 快速预览渲染不超过 3 分钟；
3. 60 秒成片 1080p 正式渲染不超过 8 分钟；
4. 草稿导出不超过 1 分钟；
5. Web 页面首屏加载不超过 3 秒；
6. SSE / WebSocket 进度延迟不超过 2 秒。

实际性能取决于服务器配置、模型 API、视频复杂度和渲染分辨率。

---

## 20. 部署要求

## 20.1 Docker Compose

建议支持 Docker Compose，包含：

```text
frontend
backend
worker
redis，可选
postgres 或 sqlite
minio，可选
```

## 20.2 Worker 镜像依赖

Worker 需要包含：

```text
Node.js 22+
Python 3.11+
FFmpeg
Chromium
HyperFrames CLI
OpenClaw runtime
Noto Sans CJK fonts
Emoji fonts
Draft exporter dependencies
ASR dependencies
Pinned HyperFrames Student Kit templates / playbook resources
```

## 20.3 存储

MVP 可使用本地目录：

```text
uploads/
outputs/
workspaces/
```

后续可切换：

1. MinIO；
2. AWS S3；
3. Cloudflare R2；
4. 阿里云 OSS；
5. 腾讯云 COS。

## 20.4 服务器建议

比赛 Demo：

```text
CPU: 8 核以上
RAM: 32GB 以上
Disk: 200GB SSD
GPU: 可选
```

更稳定测试：

```text
CPU: 16 核以上
RAM: 64GB 以上
Disk: 1TB SSD
GPU: NVIDIA 16GB+ 可选，用于本地 ASR / VLM
```

如果主要使用云端模型 API，GPU 不是必须。HyperFrames 渲染主要依赖 CPU、Chromium 和 FFmpeg。

---

## 21. 安全要求

当前阶段是单平台 Demo，不做完整多用户隔离，但仍需满足基础安全：

1. 上传文件必须重命名，禁止使用原始路径；
2. 检查 MIME 类型；
3. 限制文件大小；
4. 禁止路径穿越；
5. 不在日志中输出 API Key；
6. OpenClaw 任务尽量运行在独立 workspace；
7. Worker 不允许访问系统敏感路径；
8. 高风险 shell 命令需要禁用或拦截；
9. 定期清理临时文件。

如果未来开放公网给多人使用，必须重新设计登录、鉴权、用户隔离、API Key 加密、任务沙箱和计费系统。

---

## 22. MVP 范围

第一版必须完成：

1. 单平台项目列表；
2. 新建项目；
3. 上传口播视频、B-roll 视频、图片；
4. 用户给素材打标签和备注；
5. ASR 转录口播；
6. 简单视频 / 图片理解；
7. Agent 生成剪辑方案；
8. 生成 `asset_manifest.json`；
9. 生成 `unified_timeline.json`；
10. 接入并改造 `nateherkai/hyperframes-student-kit` 的 `/short-form-video` / `may-shorts-19` 范式，形成 MVP 高级口播模板；
11. 生成 HyperFrames 预览视频；
12. 生成剪映 / CapCut 草稿；
13. 支持下载 MP4 和草稿 zip；
14. 支持用户通过对话修改字幕、素材、节奏、BGM；
15. 支持平台级模型配置；
16. 支持任务进度显示。

第一版暂不做：

1. 登录注册；
2. 多用户；
3. 团队协作；
4. 在线支付；
5. 抖音账号直接发布；
6. 真正的小程序上线；
7. 局部渲染加速；
8. 复杂 Three.js 动画；
9. 大规模并发。

---

## 23. V1 增强功能

1. 更多视频模板；
2. 封面图生成器；
3. 自动生成爆款标题；
4. 自动生成发布文案；
5. 更多剪映草稿兼容版本；
6. 局部重渲染；
7. 时间线可视化编辑器；
8. 素材语义搜索；
9. 品牌模板；
10. 项目复制；
11. 批量生成多个版本；
12. 自动 A/B 生成 3 个开头；
13. 多用户和登录系统。

---

## 24. 验收标准

### 24.1 基础验收

给定：

1. 一个 3–5 分钟口播视频；
2. 3 个 B-roll 视频；
3. 3 张图片；
4. 每个素材都有备注；

系统应输出：

1. 一个 30–90 秒高级口播成片；
2. 成片包含字幕、B-roll、标题、动画包装、BGM；
3. 一个可下载的剪映 / CapCut 草稿；
4. 剪映 / CapCut 打开后至少能编辑视频片段、图片、字幕、音频；
5. Web 对话修改后可以生成新版本。

### 24.2 质量验收

1. 字幕与语音基本同步；
2. B-roll 插入与口播内容相关；
3. 画面比例正确；
4. 文字不超出安全区域；
5. 无明显黑屏；
6. 无明显音画错位；
7. 草稿素材路径正确；
8. 下载 zip 可正常解压；
9. 任务失败时有明确错误提示。

### 24.3 Demo 验收

比赛演示至少展示：

1. 上传素材；
2. 添加备注；
3. Agent 分析素材；
4. 自动生成视频；
5. 预览 HyperFrames 视频；
6. 下载剪映 / CapCut 草稿；
7. 打开剪映 / CapCut 草稿证明可编辑；
8. Web 对话修改一次；
9. 重新生成新版本。

---

## 25. 推荐开发顺序

### 阶段 1：核心数据结构

1. 定义 `asset_manifest.json`；
2. 定义 `unified_timeline.json`；
3. 定义 `timeline_patch.json`；
4. 定义 Draft Exporter 接口。

### 阶段 2：最小上传与分析

1. Web 上传；
2. 标签备注；
3. ASR；
4. 图片 / 视频简单理解；
5. 素材清单。

### 阶段 3：最小视频生成

1. Agent 生成剪辑计划；
2. 转 unified timeline；
3. 引入并固定 `nateherkai/hyperframes-student-kit` 参考版本；
4. 提取 `/short-form-video` 与 `may-shorts-19` 的可复用组件；
5. 生成 HyperFrames HTML；
6. 渲染 MP4。

### 阶段 4：剪映草稿导出

1. 视频轨导出；
2. 图片轨导出；
3. 字幕轨导出；
4. 音频轨导出；
5. 草稿 zip；
6. 导入测试。

### 阶段 5：对话修改

1. 聊天 UI；
2. Agent 生成 patch；
3. patch 验证；
4. 新版本生成；
5. 预览和草稿同步更新。

### 阶段 6：界面美化与比赛包装

1. 精美首页；
2. 项目展示页；
3. 进度动效；
4. Demo 素材；
5. 一键演示流程；
6. 失败兜底样例。

---

## 26. 主要风险与解决方案

### 26.1 剪映版本兼容风险

风险：不同版本剪映 / CapCut 草稿格式可能不同。

解决方案：

1. 优先支持 CapCut International；
2. 中文剪映明确推荐版本；
3. Draft Exporter 插件化；
4. 比赛 Demo 使用固定环境；
5. 导出时附带导入说明。

### 26.2 HyperFrames 效果无法完全转剪映

风险：复杂 HTML 动效无法在剪映中原生编辑。

解决方案：

1. 核心内容原生可编辑；
2. 复杂动效烘焙为 overlay；
3. 每个元素标记可编辑性；
4. 前端提示哪些元素可编辑。

### 26.2.1 Student Kit 模板依赖风险

风险：`nateherkai/hyperframes-student-kit` 是社区教学 / 示例项目，不是稳定 SDK。上游目录结构、模板实现、license 或示例代码可能变化，不能作为不可控在线依赖。

解决方案：

1. 固定参考 commit；
2. 将需要的模板和 playbook 复制到本项目 `resources/` 目录；
3. 保留来源链接和修改说明；
4. 把模板能力抽象成 `template_manifest.json`；
5. 不让核心业务逻辑直接依赖上游仓库运行时。

### 26.3 Agent 输出不稳定

风险：LLM 生成错误时间线或错误 patch。

解决方案：

1. 强制 JSON Schema；
2. patch 验证；
3. 自动修复；
4. 出错回退；
5. 保留历史版本。

### 26.4 渲染耗时过长

风险：服务器渲染慢。

解决方案：

1. 先生成 720p 快速预览；
2. 后台生成 1080p；
3. 队列处理；
4. 限制视频时长；
5. 缓存中间结果。

### 26.5 单平台模式不适合公网多人使用

风险：当前不做用户隔离，公开部署给多人使用可能造成项目混乱和数据泄露。

解决方案：

1. 当前只用于比赛 Demo 和内部测试；
2. 公网开放前增加登录和项目隔离；
3. 后续增加用户系统、权限系统和任务沙箱。

---

## 27. 外部参考资源

1. HyperFrames 官方项目与文档：用于 HTML-native 视频生成、CLI 渲染、官方 skills、composition 规范；
2. `nateherkai/hyperframes-student-kit`：用于高级短视频模板、`/short-form-video` playbook、`may-shorts-19` 口播短视频范式；
3. VectCutAPI / capcut-cli / jianying-mcp / jianying-protocol-service：用于剪映 / CapCut 草稿生成与导出；
4. OpenClaw：用于 Agent 编排、模型切换和工具调用。

参考链接：

```text
https://github.com/heygen-com/hyperframes
https://github.com/nateherkai/hyperframes-student-kit
https://github.com/sun-guannan/VectCutAPI
```

---

## 28. 项目一句话介绍

**帧造 Agent** 是一个基于 OpenClaw、HyperFrames 和剪映 / CapCut 草稿导出的 AI 口播视频重构平台。用户上传口播和素材后，Agent 自动理解内容与备注，生成高级口播短视频，并同步输出可在剪映 / CapCut 中继续修改的草稿工程。用户还可以通过 Web 对话持续修改视频，系统自动同步更新预览视频和草稿文件。
