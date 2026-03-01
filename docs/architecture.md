# OpenVort 架构设计文档

> 本文档是 OpenVort 项目的核心架构参考。涉及架构变动时必须同步更新此文档。

## 项目定位

OpenVort 是一个开源 AI 研发工作流引擎，通过 IM（企业微信/钉钉/飞书）与 AI Agent 交互，自动化项目管理、代码仓库、团队协作等研发流程。

核心理念：**Plugin 是一等公民**，所有业务能力通过插件提供，引擎本身只负责消息路由、Agent 调度和插件编排。

## 技术栈

| 层面 | 选型 |
|------|------|
| 语言 | Python 3.11+ |
| LLM | Anthropic Claude（tool use） |
| Web 框架 | FastAPI（Relay Server / 未来 Web UI） |
| CLI | Click |
| HTTP 客户端 | httpx（异步） |
| ORM | SQLAlchemy 2.0 + aiosqlite |
| 配置 | Pydantic Settings（.env + 环境变量） |
| 定时任务 | APScheduler |
| 包管理 | hatchling（PEP 621） |
| 代码规范 | Ruff |
| 测试 | pytest + pytest-asyncio |
| 协议 | Apache-2.0 |

## 核心架构

```
用户 ──→ IM 平台 ──→ Channel 适配器 ──→ Agent Runtime ──→ Plugin Tools ──→ 外部系统
          (企微/钉钉/飞书)    │              ↕    ↕              (禅道/Gitee/Jenkins)
                              │         LLM(Claude)  │
                              │              ↕        │
                              │       Plugin Prompts  │
                              │      (领域知识注入)    │
                              │                       │
                              └── Relay Server ───────┘
                                 (公网中继，可选)
```

### 分层说明

```
src/openvort/
├── config/             # 全局配置（Pydantic Settings）
│   └── settings.py     # Settings / LLMSettings / WeComSettings
├── core/               # 引擎核心（不含业务逻辑）
│   ├── agent.py        # AgentRuntime — Claude tool use agentic loop
│   ├── session.py      # SessionStore — 对话历史管理（内存，未来持久化）
│   ├── events.py       # EventBus — 异步发布/订阅事件总线
│   └── scheduler.py    # Scheduler — APScheduler 定时任务
├── plugin/             # 插件框架
│   ├── base.py         # BasePlugin / BaseChannel / BaseTool / Message
│   ├── registry.py     # PluginRegistry — Tool/Channel/Prompt 注册中心
│   └── loader.py       # PluginLoader — entry_points 自动发现 + 内置通道兜底加载
├── plugins/            # 内置插件（可独立发布为 pip 包）
│   ├── zentao/         # 禅道项目管理插件
│   │   ├── plugin.py   # ZentaoPlugin(BasePlugin) 主类
│   │   ├── config.py   # ZentaoSettings
│   │   ├── db.py       # 数据库访问层 + zt_action 审计
│   │   ├── tools/      # 7 个 Tool（任务 CRUD + Bug CRUD）
│   │   └── prompts/    # 领域知识 markdown（任务流程/Bug流程）
│   ├── vortflow/       # VortFlow 项目管理插件（内置轻量 PM）
│   │   ├── plugin.py   # VortFlowPlugin 主类
│   │   ├── config.py   # VortFlowSettings
│   │   ├── models.py   # ORM: flow_projects/stories/tasks/bugs/milestones/events
│   │   ├── engine.py   # 状态机引擎（需求→任务→Bug 全链路）
│   │   ├── notifier.py # 事件通知
│   │   ├── router.py   # FastAPI 路由（REST API）
│   │   ├── adapters/   # PMAdapter 抽象（local/zentao 双模式）
│   │   ├── tools/      # 5 个 Tool（project/intake/assign/progress/query）
│   │   └── prompts/    # 领域知识（onboarding + workflow_guide）
│   └── vortgit/        # VortGit 代码仓库管理插件
│       ├── plugin.py   # VortGitPlugin 主类
│       ├── config.py   # VortGitSettings（Fernet 加密密钥等）
│       ├── models.py   # ORM: git_providers/repos/repo_members/workspaces/code_tasks
│       ├── crypto.py   # Fernet 令牌加解密
│       ├── router.py   # FastAPI 路由（平台/仓库/提交/分支/成员）
│       ├── workspace.py # WorkspaceManager（成员隔离 Git 工作空间）
│       ├── providers/  # Git 平台抽象（base + gitee，可扩展 github/gitlab）
│       ├── tools/      # 4 个 Tool（list_repos/repo_info/query_commits/work_summary）
│       └── prompts/    # 领域知识（git_guide）
├── channels/           # IM 通道适配器
│   ├── wecom/          # 企业微信 Channel
│   │   ├── channel.py  # WeComChannel(BaseChannel)
│   │   ├── api.py      # 企微 API 客户端
│   │   ├── crypto.py   # 消息加解密
│   │   └── callback.py # Webhook 回调处理
│   ├── dingtalk/       # 钉钉 Channel
│   │   └── channel.py  # DingTalkChannel(BaseChannel)
│   └── feishu/         # 飞书 Channel
│       └── channel.py  # FeishuChannel(BaseChannel)
├── relay/              # 公网中继服务（无 AI，资源极低）
│   ├── server.py       # FastAPI 应用（接收企微回调 + REST API）
│   └── store.py        # SQLite 消息存储
├── db/                 # 数据库层
│   ├── engine.py       # SQLAlchemy async engine
│   └── models.py       # ORM 模型
├── utils/
│   └── logging.py      # 统一日志
└── cli.py              # Click CLI（init/start/tools/channels/agent）
```

## 核心概念

### Plugin（插件）

Plugin 是 OpenVort 的一等公民，是 Tool + Prompt + Config 的容器。

```python
class BasePlugin(ABC):
    name: str           # "zentao"
    display_name: str   # "禅道项目管理"
    description: str
    version: str

    def get_tools(self) -> list[BaseTool]: ...      # 返回所有 Tool
    def get_prompts(self) -> list[str]: ...          # 返回领域知识
    def validate_credentials(self) -> bool: ...      # 校验凭证
```

通过 `pyproject.toml` 的 `entry_points` 自动发现：

```toml
[project.entry-points."openvort.plugins"]
zentao = "openvort.plugins.zentao:ZentaoPlugin"
vortflow = "openvort.plugins.vortflow:VortFlowPlugin"
vortgit = "openvort.plugins.vortgit:VortGitPlugin"
```

### Tool（工具）

Tool 是 AI 可调用的原子操作，自动转换为 Claude tool use 格式。

```python
class BaseTool(ABC):
    name: str           # "zentao_create_task"
    description: str    # 给 LLM 看，影响调用决策

    def input_schema(self) -> dict: ...          # JSON Schema
    async def execute(self, params) -> str: ...  # 执行并返回结果
```

### Channel（通道）

Channel 是 IM 平台适配器，负责消息收发和格式转换。

```python
class BaseChannel(ABC):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, target, message) -> None: ...
    def on_message(self, handler) -> None: ...
```

支持三种接入模式：
- Webhook：公网直接接收回调（生产环境）
- Relay：通过中继服务器转发（本地开发无公网 IP）
- DB 轮询：兼容旧系统，轮询远程数据库

### Prompt（领域知识）

Plugin 可包含 markdown 格式的领域知识文件，在 Agent 处理消息时自动注入 system prompt，让 AI 具备该领域的业务规则和流程知识。

```
plugins/zentao/prompts/
├── task_management.md   # 任务创建/查询/更新/工时规则
└── bug_workflow.md      # Bug 创建/分级/处理流程
```

### Agent Runtime

基于 Claude tool use 的 agentic loop，不依赖 LangChain 等框架：

```
用户消息 → 加载对话历史 → 拼接 system prompt + 插件 Prompt
    → 调用 Claude API（带 tools）
    → 如果 stop_reason == tool_use：执行工具 → 回传结果 → 继续循环
    → 如果 stop_reason == end_turn：返回文本回复
    → 保存对话历史
```

### Event Bus

异步发布/订阅机制，用于模块间解耦：

```python
event_bus.on("message.received", handler)
await event_bus.emit("message.received", msg=msg)
```

### Scheduler

基于 APScheduler 的定时任务调度，支持 cron 表达式和间隔执行。

## 已实现功能

| 模块 | 功能 | 状态 |
|------|------|------|
| 引擎核心 | AgentRuntime（agentic loop + thinking + usage） | ✅ |
| 引擎核心 | SessionStore（对话历史 + compact 压缩） | ✅ |
| 引擎核心 | EventBus（事件总线） | ✅ |
| 引擎核心 | Scheduler（定时任务） | ✅ |
| 引擎核心 | LLMClient（多 Provider + Failover） | ✅ |
| 引擎核心 | AgentRouter（多 Agent 路由） | ✅ |
| 引擎核心 | IM 聊天命令（/new /status /compact /think /usage） | ✅ |
| 引擎核心 | Agent-to-Agent 通信 | ✅ |
| 插件框架 | BasePlugin / BaseTool / BaseChannel | ✅ |
| 插件框架 | PluginRegistry（注册中心） | ✅ |
| 插件框架 | PluginLoader（entry_points 自动发现） | ✅ |
| 插件框架 | Prompt 注入（领域知识 → system prompt） | ✅ |
| Channel | 企业微信（Webhook / Relay / DB轮询） | ✅ |
| Channel | 钉钉（Webhook + OpenAPI） | ✅ |
| Channel | 飞书（Event Subscription + OpenAPI） | ✅ |
| Plugin | 禅道（11 Tool + 2 Prompt，直连 MySQL） | ✅ |
| Plugin | 浏览器控制（Playwright，5 Tool） | ✅ |
| Plugin | 通讯录（5 Tool，多平台身份映射） | ✅ |
| Plugin | VortFlow 项目管理（5 Tool + 2 Prompt，状态机驱动） | ✅ |
| Plugin | VortGit 代码仓库（4 Tool + 1 Prompt，Gitee 接入） | ✅ |
| Web | 管理面板（Vue 3 + FastAPI + JWT + WebSocket） | ✅ |
| Web | VortFlow 前端（看板/需求/任务/Bug/里程碑/项目详情） | ✅ |
| Web | VortGit 前端（仓库管理/平台配置/提交分析） | ✅ |
| 安全 | RBAC 权限（admin/manager/member/guest） | ✅ |
| 安全 | DM 配对（pairing/allowlist/open） | ✅ |
| 安全 | Docker 沙箱（隔离执行） | ✅ |
| 基础设施 | Relay Server（公网中继） | ✅ |
| 基础设施 | CLI（init/start/doctor/tools/channels/agent） | ✅ |
| 基础设施 | Pydantic Settings 配置管理 | ✅ |

## 未来规划

### 近期 — VortGit 增强 + CI/CD

| 功能 | 说明 |
|------|------|
| GitHub / GitLab Provider | 扩展 VortGit 支持 GitHub 和 GitLab 平台 |
| Git Webhook 事件驱动 | push/PR/CI 事件触发 Agent 动作 |
| AI 编码集成 | CLI 工具按需安装 + AI 驱动代码提交/PR 创建 |
| Jenkins 插件 | 触发构建、查看状态、部署管理 |
| RepoDetail 页面 | VortGit 仓库详情独立页面（文件树/提交图谱） |

### 中期 — 工作流 + 报表

| 功能 | 说明 |
|------|------|
| 工作流引擎 | 可视化编排多步骤任务（审批流、发布流） |
| 统计报表插件 | 研发效能看板（ECharts 可视化） |
| Session 持久化 | 对话历史存入数据库，支持跨重启恢复 |

### 远期 — 生态 + 开放

| 功能 | 说明 |
|------|------|
| 插件市场 | 社区贡献的插件发现和安装 |
| MCP 兼容 | 支持 Model Context Protocol，对接更多 AI 工具生态 |
| @tool 装饰器 | 类似 Semantic Kernel，用装饰器快速定义 Tool |
| 插件脚手架 | `openvort plugin create my-plugin` 一键生成插件模板 |
| 国际化 | 多语言支持 |

## 设计决策记录

### 为什么不用 LangChain？

保持轻量可控。Claude tool use 原生 API 已经足够强大，agentic loop 只需约 50 行代码。引入 LangChain 会增加大量依赖和抽象层，对于我们的场景（IM → Agent → Tool）过于重量级。

### 为什么 Plugin 而不是散装 Tool？

参考 Dify、Coze、Semantic Kernel 的设计，Plugin 作为容器可以：
- 统一管理凭证（一个禅道连接供所有 Tool 共享）
- 附带领域知识（Prompt 自动注入）
- 独立发布为 pip 包
- 一键启用/禁用整组功能

### 为什么用 entry_points 而不是目录扫描？

Python entry_points 是标准的插件发现机制：
- 第三方插件 `pip install openvort-plugin-xxx` 即可自动注册
- 内置插件和外部插件使用同一套机制
- 不需要约定目录结构或配置文件

补充：为提升开发环境鲁棒性，`PluginLoader` 对内置通道（`wecom`/`dingtalk`/`feishu`）增加了兜底加载逻辑。当某些环境未正确安装 entry_points 时，仍可在运行时注册内置通道并在管理后台显示。

### 为什么需要 Relay Server？

本地开发时没有公网 IP，无法接收企微 Webhook 回调。Relay 部署在公网，只做消息中转，不跑 AI，资源占用极低（128MB 内存即可）。
