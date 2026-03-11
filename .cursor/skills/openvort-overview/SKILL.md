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
├── cli.py                   # Click CLI 入口
├── config/
│   ├── settings.py          # Pydantic Settings，env_prefix=OPENVORT_
│   └── config_service.py    # DB 驱动配置服务（优先级：DB > .env > 默认值）
├── core/                    # 引擎核心（无业务逻辑）
│   ├── agent.py             # AgentRuntime — 多 Provider agentic loop + thinking + usage
│   ├── llm.py               # LLMClient — 统一 LLM 调用层（Anthropic/OpenAI/DeepSeek）+ Failover
│   ├── context.py           # RequestContext 请求上下文
│   ├── session.py           # SessionStore 对话历史 + compact + per-session 设置
│   ├── commands.py          # IM 聊天命令（/new /status /compact /think /usage /activation）
│   ├── router.py            # AgentRouter 多 Agent 路由
│   ├── group.py             # GroupActivation 群聊激活模式（mention/always）
│   ├── group_context.py     # GroupContextManager 群聊上下文（群聊-项目关联、群 prompt）
│   ├── pairing.py           # PairingManager DM 配对安全
│   ├── sandbox.py           # SandboxManager Docker 沙箱执行
│   ├── coding_env.py        # CodingEnvironment 编码沙箱（本地/Docker 执行）
│   ├── session_tools.py     # Agent-to-Agent 通信工具（sessions_list/history/send）
│   ├── dispatcher.py        # MessageDispatcher 消息防抖/去重
│   ├── bootstrap.py         # SetupCompleteTool 首次启动向导
│   ├── setup.py             # SetupState 初始化状态
│   ├── events.py            # EventBus 事件总线
│   ├── scheduler.py         # APScheduler 定时任务
│   ├── schedule_service.py  # ScheduleService 定时任务业务层
│   ├── remote_node.py       # RemoteNodeService 远程工作节点管理
│   ├── remote_executor.py   # 远程执行器抽象（可插拔后端）
│   ├── remote_work_tool.py  # RemoteWorkTool AI 员工远程工作委派
│   ├── openclaw_executor.py # OpenClaw 执行器实现
│   ├── openclaw_ws.py       # OpenClaw WebSocket 通信
│   ├── updater.py           # 系统升级服务（版本检查 + pip 升级 + 前端下载）
│   └── prompts/bootstrap.md # 首次启动向导 prompt
├── services/                # 外部服务集成
│   ├── asr/                 # 语音识别服务（Provider: aliyun）
│   ├── tts/                 # 语音合成服务（Provider: aliyun）
│   └── embedding/           # 向量嵌入服务（Provider: dashscope）
├── plugin/                  # 插件框架
│   ├── base.py              # BasePlugin / BaseChannel / BaseTool / Message
│   ├── registry.py          # PluginRegistry 注册中心
│   └── loader.py            # PluginLoader (entry_points 自动发现)
├── plugins/
│   ├── zentao/              # 禅道插件（11 个 Tool，直连 MySQL）
│   ├── browser/             # 浏览器控制插件（Playwright，5 个 Tool）
│   ├── vortflow/            # VortFlow 项目管理插件（需求/任务/Bug 状态机，6 个 Tool）
│   ├── vortgit/             # VortGit 代码仓库插件（Git 平台接入/提交分析/工作汇报，8 个 Tool）
│   ├── jenkins/             # Jenkins CI/CD 插件（多实例管理/构建/日志，7 个 Tool）
│   ├── report/              # 汇报管理插件（日报/周报/月报生成分发，4 个 Tool）
│   ├── knowledge/           # 知识库插件（文档向量化 + 语义检索，1 个 Tool，core=True）
│   ├── schedule/            # 定时任务插件（AI 驱动定时任务管理，2 个 Tool）
│   └── system/              # 系统管理插件（通道配置 + 诊断 + 模型管理，3 个 Tool）
├── channels/
│   ├── wecom/               # 企业微信通道（智能机器人长连接 / Webhook / DB轮询 + 语音）
│   ├── dingtalk/            # 钉钉通道（Stream 长连接 / Webhook + OpenAPI + 语音）
│   ├── feishu/              # 飞书通道（WebSocket 长连接 / Event Subscription + OpenAPI + 语音）
│   └── openclaw/            # OpenClaw 多平台网关（WhatsApp/Telegram/Slack/Discord 桥接）
├── contacts/                # 通讯录（Member 中心，多平台身份映射，含 service + resolver）
├── skill/                   # Skill 知识注入（DB 驱动，三级：builtin/public/personal）
├── skills/                  # 内置 Skill 文件（7 个：developer/pm/qa/designer/assistant/code-review/daily-report）
├── auth/                    # RBAC（admin/manager/member/guest）
├── web/                     # Web 管理面板后端（FastAPI + JWT + WebSocket + SSE）
│   ├── app.py               # FastAPI 应用工厂
│   ├── auth.py              # JWT 认证模块
│   ├── deps.py              # FastAPI 依赖注入
│   ├── ws.py                # WebSocket 实时通信（presence/typing/通知）
│   ├── webhooks.py          # Webhook 触发器（外部事件 → Agent 动作）
│   └── routers/             # API 路由（27 个模块）
├── db/                      # SQLAlchemy 2.0 async + Alembic（PostgreSQL）
└── utils/logging.py

web/                         # 前端（独立目录）
├── src/
│   ├── api/index.ts         # Axios 封装
│   ├── router/              # Vue Router
│   ├── stores/              # Pinia + persistedstate
│   ├── layouts/             # BasicLayout + Header/Sidebar/Footer
│   └── views/               # overview/chat/ai-employees/ai-config/contacts/vortflow/vortgit/reports/knowledge/schedules/profile/...
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
| sqlalchemy[asyncio]>=2.0 + asyncpg | 异步 ORM（PostgreSQL） |
| alembic>=1.13 | 数据库迁移 |
| psycopg2-binary>=2.9 | PostgreSQL 同步驱动 |
| apscheduler>=3.10 | 定时任务 |
| fastapi>=0.115 + uvicorn | Web + WebSocket |
| sse-starlette>=2.0 | SSE 流式推送 |
| websockets>=13.0 | WebSocket |
| python-jose[cryptography]>=3.3 | JWT 令牌 |
| passlib[bcrypt]>=1.7 | 密码哈希 |
| python-multipart>=0.0.9 | 文件上传 |
| aiohttp>=3.9 | 异步 HTTP 客户端 |
| cryptography>=42.0 | 企微加解密 |
| pymysql>=1.1 | 禅道 MySQL |
| dashscope>=1.20 | 阿里云 DashScope（ASR/TTS/Embedding） |
| pgvector>=0.3 | PostgreSQL 向量扩展（知识库） |
| pypdf>=4.0 | PDF 解析（知识库） |
| python-docx>=1.0 | Word 文档解析（知识库） |
| lark-oapi>=1.4 | 飞书 SDK |
| lxml>=5.0 | XML 解析 |
| playwright (可选) | 浏览器控制插件 |

### 前端
Vue 3.5 + TypeScript 5.9 + Vite 7.3 + Tailwind CSS 4 + Radix Vue/Reka UI + Pinia 3 + Axios + ECharts 6 + marked 15 + TipTap（富文本）+ VeeValidate/Zod（表单验证）+ VueUse + dayjs + pinyin-pro + lucide-vue-next（图标）

## Entry Points (pyproject.toml)

```toml
[project.scripts]
openvort = "openvort.cli:main"

[project.entry-points."openvort.channels"]
wecom = "openvort.channels.wecom:WeComChannel"
dingtalk = "openvort.channels.dingtalk:DingTalkChannel"
feishu = "openvort.channels.feishu:FeishuChannel"
openclaw = "openvort.channels.openclaw:OpenClawChannel"

[project.entry-points."openvort.plugins"]
zentao = "openvort.plugins.zentao:ZentaoPlugin"
contacts = "openvort.contacts.plugin:ContactsPlugin"
vortflow = "openvort.plugins.vortflow:VortFlowPlugin"
vortgit = "openvort.plugins.vortgit:VortGitPlugin"
jenkins = "openvort.plugins.jenkins:JenkinsPlugin"
schedule = "openvort.plugins.schedule:SchedulePlugin"
report = "openvort.plugins.report:ReportPlugin"
system = "openvort.plugins.system:SystemPlugin"
browser = "openvort.plugins.browser:BrowserPlugin"
knowledge = "openvort.plugins.knowledge:KnowledgePlugin"
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
class LLMModelConfig(BaseSettings):               # 单个模型配置
    provider, api_key, api_base, model, max_tokens, timeout, api_format

class LLMSettings(BaseSettings):  # env_prefix="OPENVORT_LLM_"
    provider, api_key, api_base, model, max_tokens, timeout, api_format
    fallback_models: str = ""     # JSON: [{"provider":"openai","api_key":"...","model":"gpt-4o"}]
    def get_model_chain() -> list[dict]  # 主模型 + fallback 链

class Settings(BaseSettings):  # env_prefix="OPENVORT_"
    debug, log_level, data_dir, database_url
    llm: LLMSettings              # OPENVORT_LLM_*
    wecom: WeComSettings           # OPENVORT_WECOM_*
    feishu: FeishuSettings         # OPENVORT_FEISHU_*
    dingtalk: DingTalkSettings     # OPENVORT_DINGTALK_*
    contacts: ContactsSettings     # OPENVORT_CONTACTS_*
    org: OrgSettings               # OPENVORT_ORG_*（时区/工时/工作日）
    openclaw: OpenClawSettings     # OPENVORT_OPENCLAW_*
    web: WebSettings               # OPENVORT_WEB_*（含 auto_check_update）
```

## CLI 命令

```
openvort init                      # 交互式初始化 .env
openvort start                     # 启动服务 (--poll-db/--web/--no-web)
openvort stop                      # 停止服务
openvort restart                   # 重启服务（stop + start）
openvort doctor                    # 诊断系统配置和连接状态
openvort channels list|test        # 通道管理
openvort tools list                # 列出已注册工具
openvort plugins list              # 列出所有插件
openvort agent chat <message>      # 直接跟 Agent 对话（调试）
openvort contacts sync|list|match|accept|reject  # 通讯录管理
openvort skills list               # 列出内置 Skill（启用/禁用/创建通过 Web 面板）
openvort pairing approve|reject|list|allowlist    # DM 配对管理
openvort coding setup              # 配置 AI 编码环境（Docker 镜像 + CLI 工具 + API Key）
openvort coding status             # 查看 AI 编码环境状态
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
内置轻量项目管理，不依赖外部系统。需求→任务→Bug 全链路状态机驱动。6 个 Tool：vortflow_create_project, vortflow_intake_story, vortflow_assign, vortflow_update_progress, vortflow_query, vortflow_group_bind（群聊绑定项目）。支持 PMAdapter 抽象（本地/禅道双模式）。数据模型：flow_projects, flow_stories, flow_tasks, flow_bugs, flow_milestones, flow_events。前端页面：Board.vue（看板）、Stories/TaskTracking/Bugs/Milestones/Iterations/Versions.vue（列表）、ProjectDetail.vue（项目详情）、work-item/（工作项详情/创建组件）。

### VortGit 代码仓库插件 (plugins/vortgit/)
Git 平台接入 + 提交分析 + 多维度工作汇报 + AI 编码调度。通过 Provider 抽象支持多平台（首期 Gitee，可扩展 GitHub/GitLab）。Token 使用 Fernet 加密存储。8 个 AI Tool：git_list_repos（列出仓库）、git_repo_info（仓库详情含分支/提交）、git_query_commits（跨仓库提交查询）、git_work_summary（Git 提交 + VortFlow 任务联合分析，生成日/周/月报）、git_manage_provider（平台管理）、git_code_task（AI 编码任务：支持 repo_id 或 repo_name 智能匹配仓库→工作空间准备→CLI 执行→提交→推送→创建 PR）、git_commit_push（提交推送）、git_create_pr（创建 PR）。WorkspaceManager 提供成员隔离的本地 Git 工作空间（shallow clone + asyncio.subprocess）。CLIRunner 统一调度 CLI 编码工具（Claude Code / Aider 等），通过 CodingEnvironment（core/coding_env.py）在本地或 Docker 中执行。数据模型：git_providers, git_repos, git_repo_members, git_workspaces, git_code_tasks。前端页面：Repos.vue（仓库卡片+详情含提交/分支 Tab）、Providers.vue（平台管理）、CodeTasks.vue（编码任务）。与 VortFlow 集成：仓库通过 project_id 关联项目，git_code_task 可注入 Bug/Task/Story 上下文构建编码 prompt。

### Jenkins CI/CD 插件 (plugins/jenkins/)
Jenkins 多实例管理与 CI/CD 集成。7 个 AI Tool：jenkins_manage_instance（实例管理 CRUD）、jenkins_list_jobs（Job 列表）、jenkins_job_info（Job 详情）、jenkins_trigger_build（触发构建，含确认机制）、jenkins_build_status（构建状态）、jenkins_build_log（构建日志）、jenkins_system_info（系统信息）。数据模型：jenkins_instances。

### Report 汇报管理插件 (plugins/report/)
企业日报/周报/月报自动生成与分发。4 个 AI Tool：report_manage（汇报模板管理）、report_submit（提交汇报）、report_query（查询汇报）、report_relation（汇报关系管理）。支持 AI 自动生成汇报内容，汇报关系链上下级分发。数据模型：reports, report_templates, reporting_relations。前端页面：reports/Index.vue。

### Knowledge 知识库插件 (plugins/knowledge/)
文档上传→分块→向量化→AI 对话中语义检索。1 个 AI Tool：kb_search（知识库检索）。支持 PDF/Word/Markdown/TXT 格式。含 chunker（文档分块）、retriever（向量检索）模块。核心插件（core=True），不可禁用。依赖 pgvector 扩展和 embedding 服务。前端页面：knowledge/Index.vue。

### Schedule 定时任务插件 (plugins/schedule/)
AI 驱动的定时任务管理。2 个 AI Tool：schedule_manage（创建/更新/删除/启停/立即执行定时任务）、schedule_query（查询任务列表和详情）。支持三种调度方式：cron 定时（5段式表达式）、interval 固定间隔（秒数）、once 一次性（ISO时间）。执行方式为 agent_chat，到期后 AI 自动执行指定 prompt。底层复用 core/scheduler.py（APScheduler）+ core/schedule_service.py（CRUD 业务层）。数据模型：schedule_jobs。前端页面：schedules/Index.vue（任务列表+新建/编辑/执行）。

### System 系统管理插件 (plugins/system/)
OpenVort 系统配置与诊断。3 个 AI Tool：system_channel_config（列出/查看/更新通道配置，含引导说明和字段描述）、system_diagnose（诊断通道连通性和系统健康状态）、system_llm_config（AI 模型配置管理）。通过对话引导管理员完成通道配置：先查看可用通道 → 逐步收集配置字段 → 写入配置 → 测试连通性。核心插件（core=True），不可禁用。前端通道管理页提供 AiAssistButton 入口跳转聊天页预填引导 prompt。

## 通道系统

每个通道均有独立的 `tools.py` 提供 AI 主动发消息和语音消息工具。

### 企业微信 (channels/wecom/)
三种消息接收模式：智能机器人长连接（推荐）/ Webhook 回调 / 远程 DB 轮询。支持消息聚合、消费位点持久化、图片多模态、流式回复、思考过程显示。通道工具：SendWeComMessageTool、SendWeComVoiceTool。

### 钉钉 (channels/dingtalk/)
Stream 长连接（推荐）/ Webhook 回调。通过 OpenAPI 发送消息（oToMessages/batchSend），自动管理 access_token。支持文本和富文本消息。通道工具：SendDingTalkMessageTool、SendDingTalkVoiceTool。

### 飞书 (channels/feishu/)
WebSocket 长连接（推荐，lark-oapi SDK）/ Event Subscription 回调。通过 OpenAPI 发送消息（im/v1/messages），自动管理 tenant_access_token。支持 URL 验证和消息去重。通道工具：SendFeishuMessageTool、SendFeishuVoiceTool。

### OpenClaw (channels/openclaw/)
OpenClaw 多平台网关桥接通道。通过 OpenClaw Gateway Webhook API 双向通信，支持 WhatsApp/Telegram/Slack/Discord 等平台。入站：OpenClaw → OpenVort Webhook 回调；出站：OpenVort → OpenClaw Gateway /hooks/agent。

## 外部服务 (services/)

| 服务 | Provider | 用途 |
|------|----------|------|
| ASR 语音识别 | aliyun | IM 语音消息转写为文本 |
| TTS 语音合成 | aliyun | AI 语音消息发送 |
| Embedding 向量嵌入 | dashscope | 知识库文档向量化 + 语义检索 |

## 权限系统 (auth/)
RBAC 四角色：admin > manager > member > guest。支持插件扩展角色和权限，按职位自动映射角色。

## Web 管理面板

后端 FastAPI (src/openvort/web/)，前端 Vue 3 (web/)。后端路由共 27 个模块。

前端页面：
- 核心：overview（概览仪表盘）/ chat（SSE 流式 + 会话管理 + MemberProfile）/ ai-employees（AI 员工管理）/ ai-config（ChatModel/ModelLibrary/CodingTools/VoiceProviders）
- 项目管理：vortflow（Board/Stories/TaskTracking/Bugs/Milestones/Iterations/Versions/ProjectDetail/work-item）
- 代码仓库：vortgit（Repos/Providers/CodeTasks）
- 业务：reports（汇报中心）/ knowledge（知识库）/ schedules（定时任务）
- 管理：contacts（组织管理/部门/成员）/ plugins / channels / skills / agents（Agent 路由）/ webhooks / remote-nodes（远程工作节点）/ upgrade（系统升级）/ logs / settings
- 其他：login / profile / exception（403/404/500）

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

## 开发环境关键配置

### 数据库

**开发环境使用远程共享 PostgreSQL**，连接信息在项目根目录 `.env` 文件的 `OPENVORT_DATABASE_URL` 中配置，**不是本地 Docker**。

- **绝对不要假设数据库在 localhost**。必须读取 `.env` 获取实际连接地址和密码。
- 需要直连数据库排查问题时，从 `.env` 提取 host/port/user/password，不要用硬编码默认值。
- `init_db()` 内部：`_sync_create_all`（psycopg2 同步）和异步引擎（asyncpg）都使用同一个 `database_url`，连接的是同一个远程数据库。

### 端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 (FastAPI) | 8090 | API + WebSocket |
| 前端 (Vite dev) | 9090 | 开发服务器，`/api` 代理到 8090 |
| PostgreSQL | 见 .env | 远程共享数据库 |

## Skill 系统 (skill/ + skills/)

DB 驱动的三级 Skill 体系：
- **builtin**：内置 Skill（`src/openvort/skills/` 目录下 SKILL.md 文件，启动时自动同步到 DB）
- **public**：公共 Skill（管理员通过 Web 面板创建，所有成员可用）
- **personal**：个人 Skill（成员自建，仅本人可用）

内置 7 个 Skill：developer（开发者）、pm（项目经理）、qa（测试）、designer（设计师）、assistant（助手）、code-review（代码审查 workflow）、daily-report（日报 workflow）。

支持岗位-技能映射：默认 5 个岗位配置 + 15 个扩展岗位，创建 AI 员工时自动关联对应 Skill。

## 架构要点

- Agent Runtime 基于统一 LLM 调用层（core/llm.py），支持 Anthropic + OpenAI 兼容协议 + Failover
- Extended Thinking 支持 per-session 级别控制（off/low/medium/high）
- Token 用量追踪：per-request 和 per-session 累计，支持 IM 内 /usage 查看
- 会话压缩：LLM 摘要替换旧消息，避免 token 溢出丢失关键上下文
- IM 命令系统：/ 前缀命令在进入 Agent 前拦截处理
- Plugin 是一等公民：统一凭证管理、领域知识注入、独立发布（10 个插件）
- 内置 PM（VortFlow）：需求→任务→Bug 状态机，PMAdapter 支持本地/禅道双模式
- 内置 Git（VortGit）：多平台 Provider 抽象，Fernet 加密 Token，Git+任务联合工作汇报
- Jenkins CI/CD 集成：多实例管理、构建触发、日志查看
- 知识库：文档上传→分块→向量化→语义检索（pgvector + DashScope Embedding）
- 汇报管理：日报/周报/月报自动生成与分发
- AI 员工：虚拟成员（is_virtual），可绑定岗位和 Skill，通过定时任务自动执行工作
- 远程工作节点：RemoteWorkTool 通过可插拔执行器（OpenClaw 等）委派工作到远程节点
- 语音能力：ASR（阿里云语音识别）+ TTS（阿里云语音合成），支持语音消息收发
- 多通道：企微 + 钉钉 + 飞书 + OpenClaw，统一 BaseChannel 抽象
- 多 Agent 路由：按通道/用户/群组分发到不同 Agent 实例
- 群聊上下文：GroupContextManager 支持群聊-项目关联、群 prompt 构建
- DM 安全：配对码验证 + allowlist + 群聊 mention gating
- WebSocket 实时通信：presence + typing indicator + 通知推送
- Webhook 触发器：外部事件（CI/CD、GitHub）→ Agent 动作
- Docker 沙箱：非 main session 隔离执行
- DB 配置服务：ConfigService 优先级 DB > .env > 默认值，支持运行时配置热更新
- 系统升级：core/updater.py 版本检查 + pip 升级 + 前端静态包下载
- 数据库：PostgreSQL（asyncpg + Alembic 迁移），开发环境使用远程共享数据库（见 .env）
- 异步设计贯穿始终（asyncio + SQLAlchemy async + httpx + aiohttp）
- 详细架构文档见 `docs/architecture.md`
