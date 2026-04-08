# VortSketch — AI 驱动的 UI 原型生成器

**状态**: Phase 2 已完成 | **创建日期**: 2026-03-23

从 VortFlow 需求出发，结合 VortGit 仓库上下文，AI 生成可交互的 HTML 原型，通过对话式迭代修改，形成 **需求 → 原型 → 代码** 闭环。

## 差异化优势

| 普通 AI 原型工具 | VortSketch |
|---|---|
| 用户手动描述需求 | 直接从 VortFlow Story/Task 拉取需求描述和验收标准 |
| 每次从零生成 | 扫描 VortGit 仓库中的现有页面/组件库，保持风格一致 |
| 生成后断裂 | 原型关联到需求工作项，形成闭环 |
| 对话无记忆 | 复用 SessionStore，支持多轮迭代修改 |
| 孤立工具 | 通过 IM 通道也能用（"帮我画一下这个需求的界面"） |

## 架构

```
                  ┌──────────────────────────────┐
                  │        VortSketch 前端        │
                  │  ┌────────────┬─────────────┐ │
                  │  │  原型预览   │  对话面板    │ │
                  │  │  (iframe)  │  (SSE 流式)  │ │
                  │  └────────────┴─────────────┘ │
                  └──────────┬───────────────────┘
                             │ REST + SSE
                  ┌──────────▼───────────────────┐
                  │      VortSketch 后端          │
                  │  ┌─────────────────────────┐  │
                  │  │   SketchGenerator       │  │
                  │  │   (LLM prompt 编排)     │  │
                  │  └──┬──────────┬───────────┘  │
                  │     │          │               │
                  │  ┌──▼──┐  ┌───▼────┐          │
                  │  │Vort │  │ Vort   │          │
                  │  │Flow │  │ Git    │          │
                  │  │Slot │  │ Slot   │          │
                  │  └─────┘  └────────┘          │
                  └───────────┬───────────────────┘
                              │
                  ┌───────────▼───────────────────┐
                  │   PostgreSQL                   │
                  │   sketches + sketch_versions   │
                  └───────────────────────────────┘
```

## 技术选型

- **生成格式**: 单文件 HTML + Tailwind CSS CDN — LLM 生成质量最高，iframe 零依赖预览
- **预览方式**: `<iframe sandbox="allow-scripts allow-forms">` — 隔离安全，原生可交互
- **流式推送**: SSE（复用现有 chat SSE 模式）— AI 生成过程实时反馈
- **版本存储**: DB TEXT 字段 — 原型 HTML 一般 5-20KB，初期无需对象存储

## 目录结构

### 后端

```
src/openvort/plugins/vortsketch/
├── __init__.py                 # VortSketchPlugin(BasePlugin)
├── plugin.py                   # activate(): 注册 Tools + 挂载路由
├── generator.py                # SketchGenerator — LLM prompt 编排核心
│                               #   - 需求上下文收集 (VortFlow Slot)
│                               #   - 仓库技术栈扫描 (VortGit Slot)
│                               #   - prompt 组装 + LLM 调用
│                               #   - HTML 提取与清洗
├── models.py                   # Sketch / SketchVersion SQLAlchemy ORM
├── router.py                   # FastAPI 路由 (/api/sketches/...)
├── tools/
│   ├── __init__.py
│   ├── generate.py             # sketch_generate — AI Tool: 从描述/需求生成原型
│   └── iterate.py              # sketch_iterate  — AI Tool: 对话式迭代修改
└── prompts/
    └── sketch.md               # 原型生成专用 system prompt
```

### 前端

```
web/src/views/vortsketch/
├── Index.vue                   # 原型库首页（搜索 + 筛选 + 卡片网格）
├── Editor.vue                  # 原型编辑器（预览 + 对话 + 版本历史）
├── plugin.ts                   # 路由注册 + 侧栏菜单项
├── components/
│   ├── SketchPreview.vue       # iframe 沙箱预览（支持全屏/缩放）
│   ├── SketchChat.vue          # 右侧对话面板（SSE 流式，复用 chat 模式）
│   ├── SketchHistory.vue       # 底部版本时间线（水平滚动，点击切换）
│   ├── SketchCard.vue          # 首页原型卡片（缩略图 + 元信息）
│   └── SketchCreateDialog.vue  # 新建弹窗（名称 + 关联需求 + 描述）
└── composables/
    ├── useSketchStream.ts      # SSE 流式生成（参考 useChatStream 模式）
    └── useSketchVersions.ts    # 版本 CRUD + 切换逻辑
```

### API 模块

```
web/src/api/
└── vortsketch.ts               # 前端 API 函数（sketches CRUD + iterate + versions + export）
```

## 数据模型

```sql
CREATE TABLE sketches (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT DEFAULT '',
    project_id      INT REFERENCES flow_projects(id) ON DELETE SET NULL,
    story_id        INT DEFAULT NULL,
    story_type      VARCHAR(20) DEFAULT '',    -- story / task / bug
    created_by      INT NOT NULL REFERENCES members(id),
    current_version INT DEFAULT 1,
    is_archived     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sketch_versions (
    id              SERIAL PRIMARY KEY,
    sketch_id       INT NOT NULL REFERENCES sketches(id) ON DELETE CASCADE,
    version         INT NOT NULL,
    html_content    TEXT NOT NULL,
    instruction     TEXT DEFAULT '',            -- 用户本次修改指令
    ai_summary      VARCHAR(500) DEFAULT '',    -- AI 对本次修改的摘要
    thumbnail_url   VARCHAR(500) DEFAULT '',
    parent_version  INT DEFAULT NULL,
    tokens_used     INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(sketch_id, version)
);

CREATE INDEX idx_sketches_project ON sketches(project_id);
CREATE INDEX idx_sketches_created_by ON sketches(created_by);
CREATE INDEX idx_sketch_versions_sketch ON sketch_versions(sketch_id);
```

## API 设计

```
POST   /api/sketches                     创建原型并触发首次生成（SSE 响应）
GET    /api/sketches                     列表（分页 + project_id/keyword/is_archived 筛选）
GET    /api/sketches/:id                 详情（含当前版本 HTML）
PATCH  /api/sketches/:id                 更新元信息（名称/描述/归档）
DELETE /api/sketches/:id                 删除

POST   /api/sketches/:id/iterate         对话式迭代修改（SSE 流式响应）
GET    /api/sketches/:id/versions        版本列表
GET    /api/sketches/:id/versions/:ver   指定版本详情（含 HTML）

POST   /api/sketches/:id/export          导出（format: html / png）
```

## AI Tool 设计

| Tool | 触发场景 | 输入 | 输出 |
|------|---------|------|------|
| `sketch_generate` | IM: "帮我画个用户管理页面" | `description` + 可选 `story_id` / `project_id` | 原型链接 + 预览描述 |
| `sketch_iterate` | IM: "把搜索框改大一点" | `sketch_id` + `instruction` | 新版本链接 + 变更摘要 |

## 前端 UX 设计

### 原型库首页 (Index.vue)

```
┌─────────────────────────────────────────────────────────┐
│  VortSketch                                 [+ 新建原型] │
│  AI 驱动的 UI 原型生成器                                  │
├─────────────────────────────────────────────────────────┤
│  [搜索...]                                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ ┌────────┤  │          │  │ ┌────────┤              │
│  │ │        │  │  缩略图   │  │ │        │              │
│  │ │ 缩略图  │  │  (单页)  │  │ │ 缩略图  │              │
│  │ │(堆叠)  │  │          │  │ │(堆叠)  │              │
│  ├─┘────────┤  ├──────────┤  ├─┘────────┤              │
│  │用户管理   │  │订单详情   │  │仪表盘     │             │
│  │ 3 页面    │  │ 1 页面    │  │ 5 页面    │             │
│  │ 2小时前   │  │ 昨天      │  │ 3天前     │             │
│  └──────────┘  └──────────┘  └──────────┘              │
│                                                         │
│  空状态: 引导卡片 "描述你想要的界面，AI 帮你画出来"         │
└─────────────────────────────────────────────────────────┘
```

- 卡片悬停显示操作（归档），多页面卡片缩略图区域有堆叠纸张视觉效果
- 每张卡片展示: 名称 + 页面数量 + 描述 + 相对时间
- 关联工作项以 VortTag 展示
- 响应式网格: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`

### 新建弹窗 (SketchCreateDialog.vue)

```
┌──────────────────────────────────────────┐
│  新建原型                           [×]  │
├──────────────────────────────────────────┤
│                                          │
│  原型名称 *                              │
│  [________________________________]      │
│                                          │
│  关联需求（可选）                         │
│  [搜索需求...  ▾]                        │
│  ┌────────────────────────────────────┐  │
│  │ STORY-42 用户列表管理功能           │  │
│  │ 验收标准: 支持搜索、分页、角色筛选…  │  │
│  └────────────────────────────────────┘  │
│                                          │
│  关联项目（可选）                         │
│  [选择项目  ▾]                           │
│  → 将参考仓库中的前端技术栈和组件风格     │
│                                          │
│  界面描述 *                              │
│  ┌────────────────────────────────────┐  │
│  │ 一个用户管理后台页面，包含:          │  │
│  │ - 顶部搜索栏和新增按钮              │  │
│  │ - 用户列表表格（头像、姓名、邮箱…） │  │
│  │ - 底部分页                         │  │
│  │ (选择需求后自动填充，可修改补充)     │  │
│  └────────────────────────────────────┘  │
│                                          │
│                [取消]  [开始生成]         │
└──────────────────────────────────────────┘
```

### 原型编辑器 (Editor.vue) — 核心页面

```
┌─────────────────────────────────────────────────────────────────┐
│  ← 返回   用户管理页面   v3                                      │
│  STORY-42 · 用户列表管理功能                [全屏] [导出] [分享]  │
├─────────────────────────────────────┬───────────────────────────┤
│                                     │  ┌ 关联需求 ───────────┐  │
│                                     │  │ STORY-42             │  │
│                                     │  │ 用户列表管理功能      │  │
│                                     │  │ 验收标准: ...         │  │
│                                     │  └──────────── [折叠] ──┘  │
│    ┌─────────────────────────┐      │                           │
│    │                         │      │  ── 对话记录 ──           │
│    │                         │      │                           │
│    │    iframe 原型预览       │      │  AI  已生成用户管理页面，  │
│    │    实时渲染 HTML/CSS     │      │      包含搜索栏、表格和分页 │
│    │                         │      │                           │
│    │    支持鼠标交互          │      │  你  把表格改成卡片布局    │
│    │    (点击/输入/滚动)      │      │                           │
│    │                         │      │  AI  已将表格替换为响应式  │
│    │                         │      │      卡片网格，每张卡片包含 │
│    └─────────────────────────┘      │      头像、姓名和角色标签   │
│                                     │                           │
│    ┌─ 版本历史 ─────────────────┐   │  AI  [流式生成中...]       │
│    │                            │   │      ████████░░ 正在生成... │
│    │ v1 ──── v2 ──── v3(当前)   │   │                           │
│    │ 初始   加搜索  卡片布局     │   │                           │
│    │                            │   ├───────────────────────────┤
│    └────────────────────────────┘   │  [截图标注]  [附件]        │
│                                     │  [描述你想修改的内容...]    │
│                                     │               [发送]       │
└─────────────────────────────────────┴───────────────────────────┘
```

**UX 要点:**

- **预览区** (左): iframe 渲染，占 60% 宽度，底部版本时间线水平滚动
- **对话面板** (右): 占 40% 宽度，SSE 流式，顶部可折叠需求卡片
- **版本时间线**: 圆点 + 连线，当前版本高亮 indigo，悬停 tooltip 显示修改摘要
- **流式生成**: AI 每生成一段 HTML，iframe 实时刷新，右侧同步显示进度
- **全屏模式**: 隐藏右侧面板，预览撑满，底部浮出精简输入框
- **导出**: 下载 HTML / 复制代码 / 截图 PNG

### 交互流程

```
[+ 新建] → 填写弹窗 → [开始生成]
                            │
                    POST /api/sketches (SSE)
                            │
              ┌─────────────▼──────────────┐
              │  后端 SketchGenerator:      │
              │  1. 需求上下文 (VortFlow)    │
              │  2. 仓库扫描 (VortGit)      │
              │  3. 组装 prompt             │
              │  4. 调用 LLM (流式)         │
              └─────────────┬──────────────┘
                            │ SSE: html_chunk / done
                            ▼
              跳转 Editor → iframe 实时渲染
                            │
              用户在对话面板输入修改指令
                            │
              POST /api/sketches/:id/iterate (SSE)
                            │
                            ▼
              新版本 → 预览自动切换 → 时间线追加节点
```

## Prompt 策略

```markdown
# sketch.md (system prompt 核心要点)

你是一个 UI 原型设计专家。根据需求描述生成单文件 HTML 原型。

## 技术约束
- 使用 Tailwind CSS (CDN: https://cdn.tailwindcss.com)
- 单文件 HTML，所有样式内联或 <style>
- 基本交互用原生 JS（Tab 切换、下拉菜单、模态框等）
- 响应式设计，桌面端优先

## 设计规范
- 现代简洁风格，圆角卡片 + 微阴影
- 主色 indigo-600，中性色 gray 系列
- 间距遵循 4px 网格 (p-2/p-4/p-6)
- 字体层级: text-2xl / text-lg / text-base / text-sm
- 图标用 Lucide SVG 内联或 emoji 占位

## 输出格式
- 完整可运行的 HTML 文档 (<!DOCTYPE html> ... </html>)
- 用 <!-- section: xxx --> 注释标记主要区域
- 表格/列表使用真实感的中文示例数据

## 迭代修改
- 收到修改指令时，基于上一版本 HTML 做增量修改
- 保留未提及部分不变
- 回复格式: 先用 1-2 句话说明改了什么，再输出完整 HTML

## 上下文 (运行时动态注入)
{requirement_context}   ← VortFlow 需求描述 + 验收标准
{repo_context}          ← VortGit 仓库技术栈 + 组件风格
```

## 系统集成点

| 集成系统 | 方式 | 价值 |
|---|---|---|
| **VortFlow** | Slot 获取 Story/Task/Bug 详情 | 自动填充需求上下文 |
| **VortGit** | Slot 扫描仓库前端目录 | 推断技术栈，匹配组件风格 |
| **IM 通道** | AI Tool 注册 | 企微/钉钉/飞书中直接 "画个界面" |
| **知识库** | kb_search 检索设计规范 | 遵循团队设计规范 |
| **AI 员工** | 设计师员工自带 VortSketch | 专职设计 Agent |
| **MCP Server** | Tool 自动暴露 | Cursor / Claude Desktop 可调用 |

## 分阶段实施

| Phase | 内容 | 预估 | 状态 |
|-------|------|------|------|
| **Phase 1: 基础骨架** | 插件框架 + 数据模型 + CRUD API + 前端列表页 + iframe 预览 | 3 天 | 已完成 |
| **Phase 2: AI 生成** | SketchGenerator + sketch.md prompt + SSE 流式 + Editor 页面（预览+对话+版本） | 3 天 | 已完成 |
| **Phase 3: 对话迭代** | iterate API + 对话面板 + 版本管理 + 时间线 + useSketchStream | 3 天 | 已完成（合并到 Phase 2） |
| **Phase 4: VortFlow 集成** | 需求关联 + 上下文拉取 + 详情页入口 + AI Tool 注册 | 2 天 | 待开始 |
| **Phase 5: VortGit 感知** | 仓库扫描 + 技术栈推断 + prompt 注入 + 风格匹配 | 2 天 | 待开始 |
| **Phase 6: 体验打磨** | 缩略图生成 + 导出 + 截图标注 + 全屏模式 + 空状态引导 + IM Tool | 2 天 | 待开始 |
