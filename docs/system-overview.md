# OpenVort -- 开源 AI 研发工作流引擎

> 版本: 0.1.0 | 协议: AGPL-3.0-or-later | Python >=3.11

## 项目简介

OpenVort 是一款开源的 AI 研发工作流引擎，通过 IM（企业微信、钉钉、飞书）或 Web 管理面板与 AI Agent 交互，实现项目管理、代码仓库、团队协作、知识库检索、CI/CD 等研发全流程自动化。

核心理念：**"一切皆插件"** -- 引擎本身只负责消息路由、Agent 调度和插件编排，所有业务能力（项目管理、Git 集成、Jenkins、知识库等）均通过插件提供，`pip install` 即可扩展。

---

## 一、系统架构

### 1.1 架构总览

```
┌───────────────────────────────────────────────────────────────────┐
│                         用户入口层                                │
│  企业微信 │ 钉钉 │ 飞书 │ OpenClaw(WhatsApp/Telegram/Slack/…)    │
│                    │ Web 管理面板                                 │
└────────────┬──────────────────────────────────┬───────────────────┘
             │                                  │
┌────────────▼──────────────────────────────────▼───────────────────┐
│                       通道适配层 (Channels)                       │
│  BaseChannel 统一消息抽象 → Dispatcher 防抖/去重 → 命令拦截       │
└────────────────────────────┬──────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────┐
│                        Agent 调度层 (Core)                        │
│                                                                   │
│  AgentRouter ─→ AgentRuntime ─→ LLMClient (多 Provider Failover) │
│       │              │                                            │
│       │         Agentic Loop (最多 10 轮 tool use)                │
│       │              │                                            │
│       │         SessionStore (内存 + DB 持久化)                    │
│       │         RequestContext (身份/权限/渠道上下文)               │
│       │         AgentTaskRunner (异步任务执行引擎)                  │
│       │                                                           │
│  EventBus (模块间解耦通信)                                        │
│  SandboxManager (Docker 沙箱隔离)                                 │
│  RemoteNodeService (远程工作节点)                                  │
└────────────────────────────┬──────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────┐
│                        插件能力层 (Plugins)                       │
│                                                                   │
│  VortFlow (项目管理)  │ VortGit (代码仓库)  │ Jenkins (CI/CD)     │
│  Knowledge (知识库)   │ Report (汇报管理)   │ Schedule (定时任务)  │
│  Browser (浏览器控制) │ Zentao (禅道集成)   │ Contacts (通讯录)    │
│  System (系统管理)                                                │
└────────────────────────────┬──────────────────────────────────────┘
                             │
┌────────────────────────────▼──────────────────────────────────────┐
│                        基础设施层                                  │
│                                                                   │
│  PostgreSQL (asyncpg + pgvector)  │  Alembic (数据库迁移)         │
│  FastAPI + Uvicorn (Web 服务)     │  WebSocket (实时通信)          │
│  SSE (流式推送)                   │  APScheduler (定时任务引擎)    │
│  Docker (沙箱 + 远程节点)                                         │
└───────────────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

#### 后端

| 分类 | 技术选型 | 说明 |
|------|----------|------|
| 语言 | Python 3.11+ | 全异步架构 (asyncio) |
| Web 框架 | FastAPI + Uvicorn | API + WebSocket + SSE |
| ORM | SQLAlchemy 2.0 (async) + asyncpg | 异步数据库操作 |
| 数据库 | PostgreSQL + pgvector | 关系存储 + 向量检索 |
| 迁移 | Alembic | 数据库版本管理 |
| CLI | Click | 命令行工具 |
| 配置 | Pydantic Settings | 类型安全配置管理 |
| 定时任务 | APScheduler | 灵活的调度引擎 |
| LLM | Anthropic SDK + httpx | Claude + OpenAI 兼容协议 |
| 认证 | JWT + bcrypt | 令牌认证 + 密码哈希 |
| 向量嵌入 | DashScope Embedding | 阿里云向量化服务 |
| 语音 | DashScope ASR/TTS | 阿里云语音识别/合成 |
| 浏览器 | Playwright (可选) | 浏览器自动化控制 |

#### 前端

| 分类 | 技术选型 |
|------|----------|
| 框架 | Vue 3.5 + TypeScript 5.9 |
| 构建 | Vite 7.3 |
| 样式 | Tailwind CSS 4 |
| 组件库 | 自研 Vort 组件库 (Ant Design Vue 风格) |
| 状态管理 | Pinia 3 + persistedstate |
| HTTP | Axios |
| 图表 | ECharts 6 |
| 富文本 | TipTap |
| 图标 | lucide-vue-next |
| 工具 | VueUse + dayjs + pinyin-pro |

### 1.3 目录结构

```
src/openvort/
├── cli.py                    # Click CLI 入口（init/start/stop/restart/doctor 等）
├── config/                   # 配置管理（Pydantic Settings，DB > .env > 默认值）
├── core/                     # 引擎核心（无业务逻辑）
│   ├── agent.py              # AgentRuntime -- agentic loop + thinking + usage
│   ├── llm.py                # LLMClient -- 统一 LLM 调用 + 多 Provider + Failover
│   ├── session.py            # SessionStore -- 对话历史 + 压缩 + 多会话管理
│   ├── router.py             # AgentRouter -- 多 Agent 路由
│   ├── context.py            # RequestContext -- 请求上下文
│   ├── dispatcher.py         # MessageDispatcher -- 消息防抖/去重
│   ├── commands.py           # IM 聊天命令处理器
│   ├── events.py             # EventBus -- 事件总线
│   ├── sandbox.py            # SandboxManager -- Docker 沙箱
│   ├── remote_node.py        # RemoteNodeService -- 远程工作节点
│   ├── coding_env.py         # CodingEnvironment -- 编码沙箱
│   ├── session_tools.py      # Agent-to-Agent 通信工具
│   ├── scheduler.py          # APScheduler 定时任务引擎
│   ├── schedule_service.py   # 定时任务业务层
│   ├── updater.py            # 系统升级服务
│   ├── group.py              # 群聊激活模式
│   ├── group_context.py      # 群聊上下文管理
│   ├── pairing.py            # DM 配对安全
│   └── bootstrap.py          # 首次启动向导
├── plugin/                   # 插件框架
│   ├── base.py               # BasePlugin / BaseChannel / BaseTool / Message
│   ├── registry.py           # PluginRegistry 注册中心
│   └── loader.py             # PluginLoader (entry_points 自动发现)
├── plugins/                  # 内置插件（10 个）
│   ├── vortflow/             # 项目管理（需求/任务/缺陷/迭代/版本）
│   ├── vortgit/              # 代码仓库管理 + AI 编码
│   ├── jenkins/              # Jenkins CI/CD 集成
│   ├── knowledge/            # 知识库（向量化 + 语义检索）
│   ├── report/               # 汇报管理（日报/周报/月报）
│   ├── schedule/             # AI 定时任务
│   ├── browser/              # 浏览器控制
│   ├── zentao/               # 禅道集成
│   └── system/               # 系统管理
├── channels/                 # IM 通道适配器
│   ├── wecom/                # 企业微信
│   ├── dingtalk/             # 钉钉
│   ├── feishu/               # 飞书
│   └── openclaw/             # OpenClaw（WhatsApp/Telegram/Slack/Discord 桥接）
├── contacts/                 # 通讯录（多平台身份映射）
├── skill/                    # Skill 知识注入（三级体系）
├── skills/                   # 内置 Skill 文件（7 个角色/工作流）
├── auth/                     # RBAC 权限系统
├── services/                 # 外部服务集成（ASR/TTS/Embedding）
├── web/                      # Web 管理面板后端
│   ├── app.py                # FastAPI 应用工厂
│   ├── auth.py               # JWT 认证
│   ├── ws.py                 # WebSocket 实时通信
│   ├── webhooks.py           # Webhook 触发器
│   └── routers/              # API 路由（28 个模块）
└── db/                       # SQLAlchemy 数据库层

web/                          # 前端工程（Vue 3）
├── src/
│   ├── api/                  # Axios API 封装
│   ├── router/               # Vue Router + 菜单
│   ├── stores/               # Pinia 状态管理
│   ├── components/           # 自研 Vort 组件库 + 业务组件
│   ├── layouts/              # 页面布局
│   ├── hooks/                # 可复用 Composable
│   └── views/                # 页面视图（19 个模块，81 个文件）
└── vite.config.ts
```

---

## 二、核心引擎

### 2.1 Agent Runtime -- 自研 Agentic Loop

不依赖 LangChain 等框架，保持轻量可控。核心流程：

1. **消息接收**：从 IM 通道或 Web 面板接收用户消息
2. **上下文构建**：加载对话历史 + 发送者身份 + 渠道规范 + 群聊上下文 + AI 员工人设 + 领域知识
3. **工具过滤**：按权限、渠道、插件就绪状态过滤可用工具，按意图优先排序
4. **Agentic Loop**（最多 10 轮）：
   - 调用 LLM 获取响应（支持 Extended Thinking）
   - 若返回 `tool_use`：执行工具 -> 回传结果 -> 继续循环
   - 若返回 `end_turn`：检测空操作和通道发送缺失，必要时注入纠正提示重试
5. **结果处理**：保存对话历史 + 记录用量 + 返回结果

三种处理入口：
- `process()` -- IM 同步处理，返回完整文本
- `process_stream_im()` -- IM 流式处理，yield 事件字典
- `process_stream_web()` -- Web 面板流式处理，支持中断，实时推送工具输出

### 2.2 LLM 统一调用层 -- 多 Provider Failover

统一 LLM 响应格式，Agent 代码不直接引用具体 SDK。

**三个 Provider 实现**：

| Provider | 协议 | 适用模型 |
|----------|------|---------|
| AnthropicProvider | Anthropic Messages API | Claude 系列 |
| OpenAICompatibleProvider | Chat Completions API | GPT / DeepSeek / Moonshot / Qwen / 智谱 |
| OpenAIResponsesProvider | Responses API | GPT-5 / Codex 系列 |

**Failover 机制**：主模型 → 备用模型链，依次尝试。流式调用使用 `_FailoverStreamWrapper` 在建立连接阶段自动切换。

**特色能力**：
- Anthropic Prompt Caching（自动添加 `cache_control: ephemeral`）
- Extended Thinking 支持（off/low/medium/high 四级 budget）
- 多模态图片处理（自动格式转换）
- 统一事件流模型（跨 Provider 一致的流式事件格式）

### 2.3 会话管理 -- 内存 + DB 混合持久化

- **多会话支持**：每用户可创建多个独立会话，支持置顶/隐藏/重命名
- **会话压缩**：LLM 摘要替换旧消息，保留最近 N 条，避免 token 溢出
- **智能裁剪**：超过 max_messages 自动截断，保证 tool_use/tool_result 配对完整
- **Per-session 设置**：每个会话独立的 Thinking 级别、Usage 显示模式
- **上下文管理**：支持重置上下文 + 恢复归档消息

### 2.4 多 Agent 路由

按 channel / user_id / group_id 匹配规则，将消息路由到不同的 Agent 实例。每个 Agent 可配置：
- 独立的 LLM 模型和参数
- 独立的 System Prompt
- 独立的会话历史

### 2.5 异步任务执行引擎

Agent 执行与 SSE 解耦 -- 用户关闭页面后 AI 继续后台工作，SSE 只是"观察窗口"。

- **后台执行**：`start_task()` 启动独立 asyncio Task
- **SSE 订阅**：`subscribe()` 含历史回放，新订阅者先收到缓冲回放（最近 200 条事件）
- **协作取消**：`cancel_task()` 通过 Event 通知正在执行的 LLM 调用和工具
- **消息注入**：`inject_message()` 向运行中的任务追加指令
- **故障恢复**：服务重启时自动标记孤儿任务为 failed

### 2.6 事件总线

轻量级异步 pub/sub，用于模块间解耦通信。handler 异常隔离，单个失败不影响其他订阅者。

---

## 三、插件系统

### 3.1 插件框架

三层抽象：

- **BasePlugin**：插件容器，提供 Tools、Prompts、Config 注册，支持生命周期管理和引导流程
- **BaseTool**：AI 可调用的原子操作，自动转换为 Claude tool use 格式
- **BaseChannel**：IM 平台适配器，统一消息收发接口

插件通过 Python `entry_points` 自动发现，`pip install` 即注册。支持运行时启用/禁用。

### 3.2 VortFlow -- 敏捷项目管理

AI 驱动的全生命周期敏捷开发管理系统，不依赖外部系统。

**核心能力**：
- **工作项管理**：需求 (Story) → 任务 (Task) → 缺陷 (Bug) 全链路
- **状态机引擎**：每种工作项类型有独立状态流转，支持 TransitionHook 扩展
  - Story: intake → review → pm_refine → design → breakdown → dev_assign → in_progress → testing → done
  - Task: todo → in_progress → done → closed
  - Bug: open → confirmed → fixing → resolved → verified → closed
- **树形结构**：需求和任务支持父子层级
- **迭代管理**：Sprint 规划、进度跟踪
- **版本管理**：版本发布计划、进度百分比
- **里程碑**：关键节点标记和跟踪
- **自定义视图**：个人/共享视图 + 自定义列配置
- **工作项关联**：跨类型多对多关联（Story-Task-Bug）
- **评论系统**：支持 @mentions
- **审计日志**：所有操作记录（FlowEvent）
- **通知系统**：DB 持久化 + WebSocket 实时推送 + IM 聚合延迟通知

**AI 工具（6 个）**：需求录入、查询、分配、进度更新、创建项目、群聊绑定项目。

### 3.3 VortGit -- 代码仓库管理与 AI 编码

Git 仓库管理、AI 自动编码、提交分析、工作汇报生成。

**核心能力**：
- **多平台支持**：Gitee / GitHub / GitLab / 通用 Git，Provider 可插拔
- **仓库管理**：注册、同步、成员权限、Webhook Secret
- **AI 自动编码**：完整的 AI 编码工作流
  1. 查找仓库 → 加载 CLI 配置 → 检查编码环境
  2. 解析个人 Git Token → 自动生成分支名
  3. 构建富上下文 Prompt（注入 VortFlow Bug/Task/Story 详情 + 编码规范）
  4. 准备工作空间（浅克隆 + 创建分支）
  5. 运行 CLI 工具（Claude Code / Aider / Codex，模型链 Failover）
  6. 实时流式输出 → 提交 → 推送 → 自动创建 PR
- **工作汇报**：Git 提交 + VortFlow 任务联合分析，生成日/周/月报
- **工作空间隔离**：每成员每仓库独立克隆，asyncio.Lock 并发安全
- **Token 加密**：Fernet 对称加密存储 Git 平台 Token

**AI 工具（8 个）**：仓库列表/详情、提交查询、工作汇报、平台管理、AI 编码任务、提交推送、创建 PR。

### 3.4 Jenkins -- CI/CD 集成

**核心能力**：
- **多实例管理**：一个 OpenVort 可连接多个 Jenkins
- **Job 管理**：列表（支持 Folder/MultiBranch 递归）、详情、参数化构建
- **构建操作**：触发构建（含二次确认机制）、状态查询、日志查看
- **系统信息**：Jenkins 版本、节点状态
- **安全**：API Token Fernet 加密，写操作需用户确认

**AI 工具（7 个）**：实例管理、Job 列表/详情、触发构建、构建状态/日志、系统信息。

### 3.5 Knowledge -- 知识库

**核心能力**：
- **文档处理流水线**：上传 → 解析（PDF/DOCX/MD/TXT）→ 分块（2000 chars，200 overlap）→ Embedding → 入库
- **语义检索**：基于 pgvector 的余弦距离向量搜索
- **AI 对话集成**：Agent 可在对话中自动检索知识库相关内容
- **核心插件**：不可禁用，始终注入 AI 能力

### 3.6 Report -- 汇报管理

**核心能力**：
- **汇报类型**：日报 / 周报 / 月报 / 季报
- **模板管理**：自定义汇报模板和内容 Schema
- **自动生成**：联合 Git 提交和 VortFlow 任务进度，AI 自动撰写汇报内容
- **规则驱动**：Cron 表达式配置截止时间，支持催报和升级机制
- **汇报关系**：直线/虚线/职能汇报关系链，支持上级查看下属汇报
- **分发**：自动分发到汇报关系链上级

**AI 工具（4 个）**：模板/规则管理、提交汇报、查询汇报、关系管理。

### 3.7 Schedule -- AI 定时任务

**核心能力**：
- **调度方式**：cron 定时（5 段式）/ interval 固定间隔 / once 一次性（ISO 时间）
- **执行方式**：`agent_chat` -- 到期后 AI 自动执行指定 Prompt
- **管理操作**：创建/更新/删除/启停/立即执行

**AI 工具（2 个）**：任务管理、查询。

### 3.8 Browser -- 浏览器控制

基于 Playwright 的浏览器自动化能力。

**核心能力**：
- 导航到 URL + 自动扫描可交互元素（最多 30 个）
- 页面文本快照提取
- 截图（全页/元素/连续多张）
- 点击元素（CSS 选择器或文本匹配，失败时推荐替代元素）
- 输入文本（失败时推荐可见输入框）

**AI 工具（5 个）**：导航、快照、截图、点击、输入。

### 3.9 Zentao -- 禅道集成

直连 MySQL 数据库的禅道项目管理集成。

**核心能力**：
- 需求 (Story)、任务 (Task)、缺陷 (Bug) 的 CRUD
- 工时记录
- 审计日志 (zt_action)
- 通讯录同步
- 插件引导配置流程

**AI 工具（11 个）**：覆盖需求/任务/缺陷的创建、更新、查询、详情。

### 3.10 System -- 系统管理

**核心能力**：
- 通道配置：列出/查看/更新 IM 通道配置，对话式引导管理员完成配置
- 系统诊断：通道连通性检测和系统健康状态检查
- AI 模型配置：LLM 模型参数管理
- 核心插件，不可禁用

**AI 工具（3 个）**：通道配置、系统诊断、模型配置。

---

## 四、通道系统

### 4.1 统一接口

所有 IM 通道实现 `BaseChannel` 接口：

| 方法 | 职责 |
|------|------|
| `start()` / `stop()` | 生命周期管理 |
| `send(target, message)` | 发送消息 |
| `on_message(handler)` | 消息回调注册 |
| `get_channel_prompt()` | 渠道特有的回复风格 |
| `get_config_schema()` / `apply_config()` | 动态配置管理 |
| `test_connection()` | 连接测试 |
| `get_sync_provider()` | 通讯录同步 |

每个通道均有独立的 AI 工具用于主动发送消息和语音。

### 4.2 企业微信

- **接入方式**：智能机器人长连接（推荐，无需公网 IP）/ Webhook 回调
- **流式回复**：WebSocket stream 帧 + thinking_content 显示
- **消息聚合**：2 秒去抖窗口，同用户连续消息合并处理
- **多实例去重**：DB 级 InboxService，支持集群部署
- **多模态**：图片 AES-256-CBC 解密、语音 ASR 转写
- **消费位点持久化**：DB + 本地文件双 fallback

### 4.3 钉钉

- **接入方式**：Stream 长连接（钉钉 Gateway WebSocket）
- **AI Card 流式**：创建 AI Card 实例 → 流式内容更新 → 终态
- **消息类型**：文本、Markdown、richText、音频
- **双通道发送**：sessionWebhook 回复 + 主动消息推送

### 4.4 飞书

- **接入方式**：WebSocket 长连接（推荐，lark-oapi SDK）/ Event Subscription 回调
- **流式卡片**：创建流式卡片 → 增量 Markdown 更新 → 关闭流式模式
- **富文本解析**：Post 消息（文本 + 图片提取）
- **节流更新**：350ms 间隔防止 API 限流

### 4.5 OpenClaw

- **定位**：多平台 IM 网关桥接
- **桥接平台**：WhatsApp / Telegram / Slack / Discord 等
- **双向通信**：
  - Inbound: OpenClaw → OpenVort Webhook 回调
  - Outbound: OpenVort → OpenClaw Gateway API
- **投递通道可配**：last / whatsapp / telegram / slack / discord

---

## 五、AI 员工系统

### 5.1 概念

AI 员工是系统中的虚拟成员（`is_virtual=True`），与真人员工统一建模，可绑定：
- **岗位**：预置 20 个岗位模板（开发工程师、产品经理、测试工程师、设计师等）
- **Skill**：岗位对应的领域知识和行为规范
- **人设 Prompt**：独立的 System Prompt

### 5.2 能力扩展（互补双维度）

**远程工作节点（Outbound）**：
- 绑定远程电脑（`Member.remote_node_id`）
- AI 员工通过 `remote_work` Tool 在远程机器执行编码/命令/文件操作
- 支持两种节点类型：OpenClaw WebSocket / Docker 容器
- Token Fernet 加密，状态变更 WebSocket 广播

**Webhook 外部连接（Inbound）**：
- 通过 `WebhookConfig.member_id` 绑定 AI 员工
- 接收外部事件（GitHub/GitLab/OpenClaw）自动触发 Agent 处理
- 三种模式：agent_chat / openclaw_bridge / notify

### 5.3 创建向导

Web 面板提供四步创建向导：类型 → 岗位 → 信息 → 能力配置（可选）。

---

## 六、Skill 知识注入系统

### 6.1 三级体系

| 级别 | 来源 | 管理方式 | 可见范围 |
|------|------|----------|---------|
| 内置 (builtin) | `src/openvort/skills/` 目录 | 随系统发布，启动时同步 DB | 全局 |
| 公共 (public) | Web 面板管理员创建 | DB 管理 | 所有成员 |
| 个人 (personal) | 成员自建 | DB 管理 | 仅本人 |

### 6.2 预置 Skill

| 类型 | Skill | 说明 |
|------|-------|------|
| 角色人设 | developer / pm / qa / designer / assistant | 领域知识 + 行为规范 |
| 工作流程 | code-review / daily-report | 结构化工作流指导 |

### 6.3 岗位-技能映射

20 个预置岗位模板，每个岗位关联：
- 默认 Skill 列表
- 人设 Prompt
- 自动汇报频率

创建 AI 员工时自动关联对应 Skill。

---

## 七、通讯录与身份管理

### 7.1 以 Member 为中心

统一身份中心，一个人在企微/钉钉/飞书/Git 平台的身份统一管理。支持：
- 多平台身份映射（PlatformIdentity）
- 部门树形结构
- 汇报关系（直线/虚线/职能）

### 7.2 智能匹配

从各 IM 平台同步通讯录时，自动进行跨平台身份匹配：
- 匹配维度：email（精确 1.0）> phone（精确 0.9）> 姓名相似度
- 高置信度（>=0.9）自动关联
- 低置信度生成待确认建议

### 7.3 AI 工具

支持通过对话搜索成员（含中文称谓/昵称如"杨总""老王"的模糊匹配）。

---

## 八、权限系统

### 8.1 RBAC 四角色

| 角色 | 权限范围 |
|------|---------|
| admin | 通配权限 `*`，系统完全控制 |
| manager | 通讯录/通道/插件/技能/日志/仪表盘等管理 |
| member | 搜索/发送消息/仪表盘/计划任务 |
| guest | 无权限 |

### 8.2 扩展机制

- 插件可通过 `get_permissions()` 注册自定义权限码
- 插件可通过 `get_roles()` 注册自定义角色
- 前端路由级权限控制（`requiredRole` meta）
- 权限缓存（member_id → permission set，max 512）

---

## 九、安全机制

| 机制 | 说明 |
|------|------|
| **JWT 认证** | Web 面板和 API 访问令牌 |
| **DM 配对** | 三种策略：pairing（配对码 10 分钟有效）/ allowlist / open |
| **群聊激活** | mention 模式（仅 @时响应）/ always 模式（响应所有） |
| **Docker 沙箱** | 三种模式：off / non-main / all，限制内存/CPU/网络 |
| **Token 加密** | Git Token、Jenkins API Token 等使用 Fernet 对称加密存储 |
| **Webhook 签名** | 强制签名验证（GitHub sha256 / GitLab token / OpenClaw token） |
| **RBAC** | 四级角色 + 插件扩展权限 |
| **API Rate Limiting** | 登录接口防暴力破解 |

---

## 十、Web 管理面板

### 10.1 后端

基于 FastAPI，提供 28 个路由模块的 RESTful API。支持：
- JWT 令牌认证
- WebSocket 实时通信（在线状态 + typing 指示 + 通知推送）
- SSE 流式聊天
- Webhook 触发器
- 静态文件挂载 + SPA fallback

### 10.2 前端页面

| 分类 | 页面 | 说明 |
|------|------|------|
| 核心交互 | AI 助手聊天 | SSE 流式 + 多会话 + AI 员工对话 |
| 仪表盘 | 概览 | 数据统计 Widget |
| 研发协作 | 项目看板、需求列表、任务管理、缺陷跟踪、迭代管理、版本管理、里程碑 | VortFlow 全套 |
| 代码仓库 | 仓库管理、编码任务、Git 平台 | VortGit |
| AI 管理 | AI 员工、AI 配置（模型/语音/编码工具/模型库） | AI 能力管理 |
| 业务 | 汇报中心、知识库、计划任务 | 日常工作 |
| 组织 | 组织管理（通讯录/部门/成员） | 身份管理 |
| 系统 | 通道管理、Agent 路由、插件、Skill、Webhook、远程节点、系统升级、运行日志 | 系统配置 |
| 个人 | 登录、个人设置、通知中心 | 用户相关 |

### 10.3 实时通信

WebSocket 支持：
- **在线状态** (presence)：连接/断开时广播
- **输入指示** (typing)：正在输入广播
- **通知推送** (notification)：点对点实时通知
- **离线摘要** (offline_summary)：连接时推送未读
- **VortFlow 通知**：工作项状态变更推送

---

## 十一、CLI 命令

```
openvort init                      # 交互式初始化 .env
openvort start                     # 启动服务 (--web/--no-web)
openvort stop                      # 停止服务
openvort restart                   # 重启服务
openvort doctor                    # 诊断系统配置和连接状态
openvort channels list|test        # 通道管理
openvort tools list                # 列出已注册工具
openvort plugins list              # 列出所有插件
openvort agent chat <message>      # 直接跟 Agent 对话（调试）
openvort contacts sync|list|match  # 通讯录管理
openvort skills list               # 列出内置 Skill
openvort pairing approve|reject    # DM 配对管理
openvort coding setup|status       # AI 编码环境管理
```

---

## 十二、IM 聊天命令

在所有 IM 通道中支持 `/` 前缀命令：

| 命令 | 功能 |
|------|------|
| `/new` `/reset` | 重置会话 |
| `/status` | 查看模型、消息数、token 用量 |
| `/compact` | LLM 摘要压缩上下文 |
| `/think <off\|low\|medium\|high>` | 设置 Extended Thinking 级别 |
| `/usage <off\|tokens\|full>` | 设置 token 用量显示模式 |
| `/activation <mention\|always>` | 群聊激活模式 |
| `/help` | 显示帮助 |

---

## 十三、外部服务集成

| 服务 | Provider | 用途 |
|------|----------|------|
| ASR 语音识别 | 阿里云 DashScope | IM 语音消息转写为文本 |
| TTS 语音合成 | 阿里云 DashScope | AI 语音消息发送 |
| Embedding 向量嵌入 | 阿里云 DashScope | 知识库文档向量化 + 语义检索 |

---

## 十四、系统特点与优势

### 14.1 架构优势

| 特点 | 说明 |
|------|------|
| **自研 Agentic Loop** | 不依赖 LangChain，核心循环约 50 行，轻量、可控、易调试 |
| **一切皆插件** | Tool + Prompt + Config 容器化，pip install 即可扩展 |
| **entry_points 自动发现** | 零配置插件注册，符合 Python 生态标准 |
| **全异步架构** | asyncio 贯穿全栈，高并发低延迟 |
| **多 Provider Failover** | 主模型失败自动切换备用，保障服务可用性 |
| **SSE + Task 解耦** | 用户离开页面 AI 继续工作，回来可续接 |
| **DB 配置服务** | 运行时配置热更新（DB > .env > 默认值） |

### 14.2 AI 能力优势

| 特点 | 说明 |
|------|------|
| **Extended Thinking** | Per-session 级别控制，复杂任务深度推理 |
| **Prompt Caching** | Anthropic 原生缓存，降低重复调用成本 |
| **空操作纠正** | 自动检测 LLM"声称完成但没行动"的情况并重试 |
| **AI 自动编码** | 从需求/Bug 到代码提交/PR 的全自动化 |
| **AI 员工** | 虚拟成员绑定岗位，定时自动执行任务 |
| **知识库 RAG** | 文档向量化 + 对话中自动语义检索 |
| **Skill 知识注入** | 三级体系，领域知识和行为规范精准注入 |

### 14.3 研发协作优势

| 特点 | 说明 |
|------|------|
| **需求→代码全链路** | VortFlow 需求 → VortGit AI 编码 → Jenkins 构建 |
| **状态机驱动** | 工作项状态流转自动化，支持 Hook 扩展 |
| **多平台 IM** | 企微/钉钉/飞书/全球 IM 统一接入 |
| **流式 AI 回复** | 三大 IM 平台均支持流式卡片/消息 |
| **跨平台身份统一** | 一人多平台身份自动匹配和映射 |
| **智能通知聚合** | IM 通知 30 秒聚合，防消息轰炸 |

### 14.4 安全与可靠性

| 特点 | 说明 |
|------|------|
| **RBAC + 插件权限** | 四级角色 + 插件可扩展权限体系 |
| **Docker 沙箱** | 非受信会话隔离执行，限制资源 |
| **DM 配对** | 防止未授权用户与 AI 对话 |
| **Token 加密存储** | Fernet 对称加密，密钥本地持久化 |
| **Webhook 签名验证** | 防伪造外部事件 |
| **会话位点持久化** | 重启后恢复消息处理进度 |

### 14.5 部署与运维

| 特点 | 说明 |
|------|------|
| **一键安装** | `pip install openvort && openvort init && openvort start` |
| **Docker Compose** | 单命令容器化部署 |
| **系统诊断** | `openvort doctor` 一键检查配置和连接 |
| **自动升级** | 版本检查 + pip 升级 + 前端包下载 |
| **运行日志** | Web 面板实时查看 |

---

## 十五、数据模型概览

系统核心数据模型分布在以下领域：

| 领域 | 主要模型 | 数量 |
|------|---------|------|
| VortFlow | Project, Story, Task, Bug, Iteration, Version, Milestone, Event, View, Comment, Link, ExternalMapping | 17 |
| VortGit | GitProvider, GitRepo, GitRepoMember, GitWorkspace, GitCodeTask | 5 |
| Jenkins | JenkinsInstance | 1 |
| Knowledge | KBDocument, KBChunk (pgvector) | 2 |
| Report | Report, ReportTemplate, ReportRule | 3 |
| Contacts | Member, PlatformIdentity, Department, MatchSuggestion, ReportingRelation, OrgCalendar | 7 |
| Auth | Role, Permission, MemberRole, RolePermission | 4 |
| Session | Session (DB 持久化) | 1 |
| Schedule | ScheduleJob | 1 |
| Skill | Skill | 1 |
| Webhook | WebhookConfig | 1 |
| RemoteNode | RemoteNode | 1 |
| Config | ConfigEntry | 1 |
| Agent | AgentConfig | 1 |

---

*本文档基于 OpenVort v0.1.0 编写，最后更新：2026-03-16*
