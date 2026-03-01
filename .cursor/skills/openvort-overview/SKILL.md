---
name: openvort-overview
description: OpenVort 项目全局上下文。提供项目结构、技术栈、核心模块、关键类签名等信息，避免每次对话重复探索代码库。任何涉及 OpenVort 开发、调试、重构的任务都应参考此 Skill。
---

# OpenVort 项目概览

开源 AI 研发工作流引擎 — 通过 IM 与 AI 交互，自动化项目管理、代码仓库、团队协作。

- 许可证: Apache-2.0
- Python: >=3.11
- 构建: hatchling

## 目录结构

```
src/openvort/
├── __init__.py              # 版本号
├── __main__.py
├── cli.py                   # Click CLI 入口（含 doctor/pairing 命令）
├── config/settings.py       # Pydantic Settings，env_prefix=OPENVORT_
├── core/                    # 引擎核心（无业务逻辑）
│   ├── agent.py             # AgentRuntime — 多 Provider agentic loop + thinking + usage
│   ├── llm.py               # LLMClient — 统一 LLM 调用层（Anthropic/OpenAI/DeepSeek）+ Failover
│   ├── context.py           # RequestContext 请求上下文
│   ├── session.py           # SessionStore 对话历史 + compact + per-session 设置
│   ├── commands.py          # IM 聊天命令（/new /status /compact /think /usage /activation）
│   ├── router.py            # AgentRouter 多 Agent 路由
│   ├── group.py             # GroupActivation 群聊激活模式（mention/always）
│   ├── pairing.py           # PairingManager DM 配对安全
│   ├── sandbox.py           # SandboxManager Docker 沙箱执行
│   ├── session_tools.py     # Agent-to-Agent 通信工具（sessions_list/history/send）
│   ├── dispatcher.py        # MessageDispatcher 消息防抖/去重
│   ├── bootstrap.py         # SetupCompleteTool 首次启动向导
│   ├── setup.py             # SetupState 初始化状态
│   ├── events.py            # EventBus 事件总线
│   ├── scheduler.py         # APScheduler 定时任务
│   └── schedule_service.py  # ScheduleService 定时任务业务层
├── plugin/                  # 插件框架
│   ├── base.py              # BasePlugin / BaseChannel / BaseTool / Message
│   ├── registry.py          # PluginRegistry 注册中心
│   └── loader.py            # PluginLoader (entry_points 自动发现)
├── plugins/
│   ├── zentao/              # 禅道插件（11 个 Tool，直连 MySQL）
│   ├── browser/             # 浏览器控制插件（Playwright，5 个 Tool）
│   ├── vortflow/            # VortFlow 项目管理插件（需求/任务/Bug 状态机，5 个 Tool）
│   └── vortgit/             # VortGit 代码仓库插件（Git 平台接入/提交分析/工作汇报，4 个 Tool）
├── channels/
│   ├── wecom/               # 企业微信通道（Webhook/Relay/DB轮询）
│   ├── dingtalk/            # 钉钉通道（Webhook 回调 + OpenAPI）
│   └── feishu/              # 飞书通道（Event Subscription + OpenAPI）
├── contacts/                # 通讯录（Member 中心，多平台身份映射）
├── skill/                   # Skill 知识注入系统
├── auth/                    # RBAC（admin/manager/member/guest）
├── relay/                   # 公网中继服务（轻量 FastAPI + SQLite）
├── web/                     # Web 管理面板后端（FastAPI + JWT + WebSocket）
│   ├── app.py               # FastAPI 应用工厂
│   ├── ws.py                # WebSocket 实时通信（presence/typing）
│   ├── webhooks.py          # Webhook 触发器（外部事件 → Agent 动作）
│   └── routers/             # API 路由
├── db/                      # SQLAlchemy 2.0 async（SQLite/PostgreSQL）
└── utils/logging.py

web/                         # 前端（独立目录）
├── src/
│   ├── api/index.ts         # Axios 封装
│   ├── router/              # Vue Router
│   ├── stores/              # Pinia
│   ├── layouts/             # BasicLayout + Header/Sidebar/Footer
│   └── views/               # login/chat/workspace/dashboard/profile + admin + vortflow + vortgit 页面
├── package.json
└── vite.config.ts
```

## 技术栈

### 后端
| 依赖 | 用途 |
|------|------|
| anthropic>=0.40 | Claude LLM API |
| httpx>=0.27 | 异步 HTTP（OpenAI 兼容 Provider / 钉钉 / 飞书 API） |
| click>=8.1 | CLI |
| pydantic>=2.0 + pydantic-settings | 配置 |
| sqlalchemy[asyncio]>=2.0 + aiosqlite | 异步 ORM |
| apscheduler>=3.10 | 定时任务 |
| fastapi>=0.115 + uvicorn | Web + Relay + WebSocket |
| cryptography>=42.0 | 企微加解密 |
| pymysql>=1.1 | 禅道 MySQL |
| playwright (可选) | 浏览器控制插件 |

### 前端
Vue 3.5 + TypeScript 5.9 + Vite 7.3 + Tailwind CSS 4 + Radix Vue/Reka UI + Pinia 3 + Axios + ECharts 6 + marked 15

## Entry Points (pyproject.toml)

```toml
[project.scripts]
openvort = "openvort.cli:main"

[project.entry-points."openvort.channels"]
wecom = "openvort.channels.wecom:WeComChannel"
dingtalk = "openvort.channels.dingtalk:DingTalkChannel"
feishu = "openvort.channels.feishu:FeishuChannel"

[project.entry-points."openvort.plugins"]
zentao = "openvort.plugins.zentao:ZentaoPlugin"
contacts = "openvort.contacts.plugin:ContactsPlugin"
vortflow = "openvort.plugins.vortflow:VortFlowPlugin"
vortgit = "openvort.plugins.vortgit:VortGitPlugin"
```

## 核心类签名

### LLMClient (core/llm.py)
```python
class LLMClient:
    """带 Failover 的统一 LLM 客户端"""
    def __init__(self, models: list[dict])                    # 模型链（主 + fallback）
    async def create(*, system, messages, tools, thinking)    # 同步调用（自动 failover）
    def stream(*, system, messages, tools, thinking)          # 流式调用（主模型）
    primary_model: str                                        # 当前主模型名

class AnthropicProvider(LLMProvider): ...   # Anthropic Claude
class OpenAICompatibleProvider(LLMProvider): ...  # OpenAI/DeepSeek/Moonshot/通义 等
```

### AgentRuntime (core/agent.py)
```python
class AgentRuntime:
    def __init__(self, llm_settings, registry, session_store, system_prompt)
    async def process(self, ctx: RequestContext, content: str) -> str       # agentic loop + thinking + usage
    async def chat(self, content: str) -> str                               # CLI 调试用
    async def process_stream_web(self, content, member_id="admin")          # Web SSE 流式 + usage
```

### SessionStore (core/session.py)
```python
class SessionStore:
    async def get_messages(channel, user_id) -> list[dict]
    async def save_messages(channel, user_id, messages)
    async def clear(channel, user_id)
    async def compact(channel, user_id, llm_client, keep_recent=10) -> str  # 会话压缩
    def set_thinking_level(channel, user_id, level)   # per-session thinking
    def set_usage_mode(channel, user_id, mode)        # per-session 用量显示
    def add_usage(channel, user_id, input_tokens, output_tokens)
    def get_session_info(channel, user_id) -> dict
```

### CommandHandler (core/commands.py)
```python
class CommandHandler:
    """IM 聊天命令处理器"""
    async def handle(channel, user_id, content) -> CommandResult
    # 支持: /new /reset /status /compact /think /usage /activation /help
```

### AgentRouter (core/router.py)
```python
class AgentRouter:
    """多 Agent 路由器"""
    def add_agent(config: AgentConfig)
    def route(channel, user_id, group_id="") -> RouteMatch
```

### RequestContext (core/context.py)
```python
@dataclass
class RequestContext:
    channel: str            # wecom/dingtalk/cli
    user_id: str            # 平台 user_id
    member: Member | None   # 解析后的成员
    roles: list[str]
    permissions: set[str]
    images: list[dict]      # 多模态图片
    platform_accounts: dict[str, str]  # {platform: account}
    async def refresh_identity(self) -> None
    def get_sender_prompt(self) -> str
    def has_permission(self, permission: str) -> bool
```

### Settings (config/settings.py)
```python
class LLMSettings(BaseSettings):  # env_prefix="OPENVORT_LLM_"
    provider, api_key, api_base, model, max_tokens, timeout
    fallback_models: str = ""     # JSON: [{"provider":"openai","api_key":"...","model":"gpt-4o"}]
    def get_model_chain() -> list[dict]  # 主模型 + fallback 链

class Settings(BaseSettings):  # env_prefix="OPENVORT_"
    debug, log_level, data_dir, database_url
    llm: LLMSettings           # OPENVORT_LLM_*
    wecom: WeComSettings        # OPENVORT_WECOM_*
    relay: RelaySettings        # OPENVORT_RELAY_*
    contacts: ContactsSettings  # OPENVORT_CONTACTS_*
    web: WebSettings            # OPENVORT_WEB_*
```

## CLI 命令

```
openvort init                      # 交互式初始化 .env
openvort start                     # 启动服务 (--relay-url/--poll-db/--web/--no-web)
openvort doctor                    # 诊断系统配置和连接状态
openvort channels list|test        # 通道管理
openvort tools list                # 列出已注册工具
openvort plugins list              # 列出所有插件
openvort agent chat <message>      # 直接跟 Agent 对话（调试）
openvort contacts sync|list|match|accept|reject  # 通讯录管理
openvort skills list|enable|disable|create        # Skill 管理
openvort pairing approve|reject|list|allowlist    # DM 配对管理
```

## 插件系统

插件通过 `entry_points` 自动发现，`pip install` 即注册。

### 插件框架 (plugin/)
- `BasePlugin`: 插件基类，提供 tools/prompts/config 注册
- `BaseChannel`: 通道基类，消息收发抽象
- `BaseTool`: 工具基类，定义 name/description/input_schema/execute
- `PluginRegistry`: 注册中心，管理所有插件和工具
- `PluginLoader`: 通过 entry_points 扫描加载

### 禅道插件 (plugins/zentao/)
直连 MySQL，11 个 Tool：create/update/my_tasks, task_detail, log_effort, create/update/my_bugs, create/update/my_stories。支持 zt_action 审计日志、通讯录同步、插件引导流程。

### 浏览器控制插件 (plugins/browser/)
基于 Playwright，5 个 Tool：browser_navigate, browser_snapshot, browser_screenshot, browser_click, browser_type。需安装 playwright。

### 通讯录插件 (contacts/)
5 个 Tool：sync_contacts, search_member, match_suggestions, resolve_match, bind_identity。以 Member 为中心，PlatformIdentity 实现多平台身份映射，智能匹配（email/phone/name 多维度）。

### VortFlow 项目管理插件 (plugins/vortflow/)
内置轻量项目管理，不依赖外部系统。需求→任务→Bug 全链路状态机驱动。5 个 Tool：vortflow_create_project, vortflow_intake_story, vortflow_assign, vortflow_update_progress, vortflow_query。支持 PMAdapter 抽象（本地/禅道双模式）。数据模型：flow_projects, flow_stories, flow_tasks, flow_bugs, flow_milestones, flow_events。前端页面：Board.vue（看板）、Stories/Tasks/Bugs/Milestones.vue（列表）、ProjectDetail.vue（项目详情）。

### VortGit 代码仓库插件 (plugins/vortgit/)
Git 平台接入 + 提交分析 + 多维度工作汇报。通过 Provider 抽象支持多平台（首期 Gitee，可扩展 GitHub/GitLab）。Token 使用 Fernet 加密存储。4 个 AI Tool：git_list_repos（列出仓库）、git_repo_info（仓库详情含分支/提交）、git_query_commits（跨仓库提交查询）、git_work_summary（Git 提交 + VortFlow 任务联合分析，生成日/周/月报）。WorkspaceManager 提供成员隔离的本地 Git 工作空间（shallow clone + asyncio.subprocess）。数据模型：git_providers, git_repos, git_repo_members, git_workspaces, git_code_tasks。前端页面：Repos.vue（仓库卡片+详情含提交/分支 Tab）、Providers.vue（平台管理）。与 VortFlow 集成：仓库通过 project_id 关联项目，ProjectDetail.vue 展示关联仓库。

## 通道系统

### 企业微信 (channels/wecom/)
三种消息接收模式：Webhook 回调 / Relay 中继 / 远程 DB 轮询。支持消息聚合、消费位点持久化、图片多模态。

### 钉钉 (channels/dingtalk/)
Webhook 回调模式。通过 OpenAPI 发送消息（oToMessages/batchSend），自动管理 access_token。支持文本和富文本消息。

### 飞书 (channels/feishu/)
Event Subscription 回调模式。通过 OpenAPI 发送消息（im/v1/messages），自动管理 tenant_access_token。支持 URL 验证和消息去重。

## 权限系统 (auth/)
RBAC 四角色：admin > manager > member > guest。支持插件扩展角色和权限，按职位自动映射角色。

## Web 管理面板

后端 FastAPI (src/openvort/web/)，前端 Vue 3 (web/)。

路由：login / chat(SSE流式) / workspace / dashboard / schedules / profile + admin(contacts/plugins/channels/skills/logs/settings) + vortflow(Board/Stories/Tasks/Bugs/Milestones/ProjectDetail) + vortgit(Repos/Providers)

实时通信：WebSocket (ws.py) 支持 presence 在线状态、typing indicator、实时通知推送。

Webhook 触发器：POST /api/webhooks/<name>，支持 GitHub 事件解析、签名验证、agent_chat/notify 动作。

前端构建产物 `web/dist/` 由后端静态挂载 + SPA fallback。

## IM 聊天命令

在所有 IM 通道中支持 / 前缀命令（core/commands.py）：
- `/new` `/reset` — 重置会话
- `/status` — 查看模型、消息数、token 用量
- `/compact` — LLM 摘要压缩上下文
- `/think <off|low|medium|high>` — 设置 Extended Thinking 级别
- `/usage <off|tokens|full>` — 设置 token 用量显示模式
- `/activation <mention|always>` — 群聊激活模式
- `/help` — 显示帮助

## 安全机制

### DM 配对 (core/pairing.py)
三种策略：pairing（配对码验证）/ allowlist（白名单）/ open（开放）。配对码 10 分钟有效，管理员通过 CLI 批准。allowlist 持久化到 ~/.openvort/dm_allowlist.json。

### 群聊激活 (core/group.py)
mention 模式（默认）：只在被 @mention 时响应。always 模式：响应所有消息。支持按群组 ID 覆盖和运行时切换。

### Docker 沙箱 (core/sandbox.py)
三种模式：off / non-main / all。非 main session 在 Docker 容器中隔离执行命令，限制内存/CPU/网络。

## 多 Agent 路由 (core/router.py)

按 channel / user_id / group_id 匹配路由规则，将消息路由到不同的 Agent 实例。每个 Agent 可有独立的模型配置和 system prompt。

## Agent-to-Agent 通信 (core/session_tools.py)

三个 AI Tool：sessions_list（列出活跃会话）、sessions_history（查看历史）、sessions_send（跨会话发消息）。

## 架构要点

- Agent Runtime 基于统一 LLM 调用层（core/llm.py），支持 Anthropic + OpenAI 兼容协议 + Failover
- Extended Thinking 支持 per-session 级别控制（off/low/medium/high）
- Token 用量追踪：per-request 和 per-session 累计，支持 IM 内 /usage 查看
- 会话压缩：LLM 摘要替换旧消息，避免 token 溢出丢失关键上下文
- IM 命令系统：/ 前缀命令在进入 Agent 前拦截处理
- Plugin 是一等公民：统一凭证管理、领域知识注入、独立发布
- 内置 PM（VortFlow）：需求→任务→Bug 状态机，PMAdapter 支持本地/禅道双模式
- 内置 Git（VortGit）：多平台 Provider 抽象，Fernet 加密 Token，Git+任务联合工作汇报
- 多通道：企微 + 钉钉 + 飞书，统一 BaseChannel 抽象
- 多 Agent 路由：按通道/用户/群组分发到不同 Agent 实例
- DM 安全：配对码验证 + allowlist + 群聊 mention gating
- WebSocket 实时通信：presence + typing indicator + 通知推送
- Webhook 触发器：外部事件（CI/CD、GitHub）→ Agent 动作
- Docker 沙箱：非 main session 隔离执行
- Relay Server 解决本地开发无公网 IP 问题
- 异步设计贯穿始终（asyncio + SQLAlchemy async + httpx）
- 详细架构文档见 `docs/architecture.md`
