# OpenVort

开源 AI 研发工作流引擎 — 通过 IM 或 Web 面板与 AI Agent 交互，自动化项目管理、代码仓库、团队协作。

## 特性

- **AI 驱动** — 基于 Claude tool use 的 agentic loop，Agent 自主决策调用工具，支持多模型 Failover
- **AI 员工** — 虚拟成员绑定岗位与 Skill，通过定时任务自动执行日报/代码审查/测试等工作
- **多 IM 支持** — 企业微信、钉钉、飞书、OpenClaw 多平台网关，支持语音消息收发（ASR/TTS）
- **Web 管理面板** — Vue 3 + FastAPI，支持 AI 聊天（SSE 流式）、概览仪表盘、AI 配置中心、项目管理、代码仓库、知识库、汇报、定时任务等
- **插件化架构** — Plugin 是一等公民，Channel（IM 通道）和 Plugin（Tool + Prompt）均可插拔，`pip install` 即可扩展
- **内置 10 个插件** — 禅道、VortFlow 敏捷流程、VortGit 代码仓库、Jenkins CI/CD、知识库（RAG）、汇报管理、定时任务、浏览器自动化、系统管理
- **Skill 知识注入** — 三级 Skill 体系（内置/公共/个人），7 个内置 Skill 按岗位自动映射
- **安全** — RBAC 四级权限、DM 配对、Docker 沙箱、Token 加密

## 架构

```
用户 ──→ IM 平台 ──→ Channel 适配器 ──→ Dispatcher ──→ Agent Runtime ──→ Plugin Tools ──→ 外部系统
     (企微/钉钉/飞书)   │                  (防抖/去重)     ↕    ↕              (禅道/Gitee/...)
                        │                            LLM(Claude)  │
          Web 面板 ─────┤                                         │
         (Vue 3 SPA)    └─────────────────────────────────────────┘
```

## 快速开始

### 本地开发

```bash
# 克隆仓库
git clone https://github.com/nicekate/openvort.git
cd openvort

# 安装后端（editable 模式）
pip install -e ".[dev]"

# 复制并编辑环境变量
cp .env.example .env
# 至少配置 OPENVORT_LLM_API_KEY

# 启动（后端 + Web 面板）
openvort start --web
```

### Docker 部署

```bash
# 复制并编辑环境变量
cp .env.example .env

# 一键启动（含 PostgreSQL）
docker compose up -d
```

默认端口 `8090`，访问 `http://localhost:8090` 进入 Web 管理面板。

### 前端单独开发

```bash
cd web
npm install
npm run dev   # Vite dev server，默认 http://localhost:9090，/api 代理到 8090
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENVORT_LLM_API_KEY` | LLM API Key（必填） | — |
| `OPENVORT_LLM_MODEL` | 模型名称 | `claude-sonnet-4-20250514` |
| `OPENVORT_LLM_PROVIDER` | 提供商（anthropic / openai_compatible） | `anthropic` |
| `OPENVORT_DATABASE_URL` | 数据库连接 | PostgreSQL（本地开发） |
| `OPENVORT_LOG_LEVEL` | 日志级别 | `INFO` |
| `OPENVORT_WEB_PORT` | Web 面板端口 | `8090` |
| `OPENVORT_WEB_DEFAULT_PASSWORD` | 成员默认登录密码 | `openvort` |

完整配置参考 [`.env.example`](.env.example)。

### IM 通道配置

**企业微信**：支持智能机器人长连接（推荐）/ Webhook / DB 轮询。配置 `OPENVORT_WECOM_*` 系列变量。

**钉钉**：推荐 Stream 长连接模式，配置 `OPENVORT_DINGTALK_APP_KEY`、`OPENVORT_DINGTALK_APP_SECRET`、`OPENVORT_DINGTALK_ROBOT_CODE`。流式输出额外配置 `OPENVORT_DINGTALK_MESSAGE_TYPE=card` + 卡片模板。

**飞书**：推荐 WebSocket 长连接模式，配置 `OPENVORT_FEISHU_APP_ID`、`OPENVORT_FEISHU_APP_SECRET`。

**OpenClaw**：多平台网关（WhatsApp/Telegram/Slack/Discord），配置 `OPENVORT_OPENCLAW_GATEWAY_URL`、`OPENVORT_OPENCLAW_HOOK_TOKEN`。

## 项目结构

```
src/openvort/
├── core/           # 引擎核心（Agent Runtime / LLM Client / Session / Dispatcher / 远程节点 / 升级服务）
├── config/         # 配置（Pydantic Settings + DB 配置服务）
├── plugin/         # 插件框架（BasePlugin / BaseTool / Registry / Loader）
├── plugins/        # 内置插件（禅道 / VortFlow / VortGit / Jenkins / 知识库 / 汇报 / 浏览器 / 定时任务 / 系统）
├── channels/       # IM 通道（企微 / 钉钉 / 飞书 / OpenClaw，含语音工具）
├── contacts/       # 通讯录（多平台身份映射 + Service + Resolver）
├── services/       # 外部服务集成（ASR 语音识别 / TTS 语音合成 / Embedding 向量嵌入）
├── skill/          # Skill 加载器（DB 驱动三级体系）
├── skills/         # 内置 Skill 文件（7 个 SKILL.md）
├── auth/           # RBAC 权限
├── web/            # Web 面板后端（FastAPI + JWT + WebSocket + SSE，27 个路由模块）
├── db/             # 数据库（SQLAlchemy 2.0 async + Alembic 迁移）
└── cli.py          # CLI 入口

web/                # 前端（Vue 3.5 + TypeScript 5.9 + Vite 7 + Tailwind CSS 4）
```

详细架构设计参见 [`docs/architecture.md`](docs/architecture.md)。

## 开发命令

```bash
make install   # pip install -e ".[dev]"
make dev       # openvort start
make test      # pytest -v
make lint      # ruff check
make format    # ruff format
```

## 协议

[Apache-2.0](LICENSE)
