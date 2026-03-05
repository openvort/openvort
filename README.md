# OpenVort

开源 AI 研发工作流引擎 — 通过 IM 或 Web 面板与 AI Agent 交互，自动化项目管理、代码仓库、团队协作。

## 特性

- **AI 驱动** — 基于 Claude tool use 的 agentic loop，Agent 自主决策调用工具，支持多模型 Failover
- **多 IM 支持** — 企业微信、钉钉、飞书、OpenClaw 多平台网关
- **Web 管理面板** — Vue 3 + FastAPI，支持 AI 聊天（SSE 流式）、项目管理、代码仓库、通讯录、定时任务、汇报等
- **插件化架构** — Plugin 是一等公民，Channel（IM 通道）和 Plugin（Tool + Prompt）均可插拔，`pip install` 即可扩展
- **内置业务插件** — 禅道、VortFlow 敏捷流程、VortGit 代码仓库、汇报管理、定时任务、浏览器自动化等
- **安全** — RBAC 四级权限、DM 配对、Docker 沙箱、Token 加密

## 架构

```
用户 ──→ IM 平台 ──→ Channel 适配器 ──→ Dispatcher ──→ Agent Runtime ──→ Plugin Tools ──→ 外部系统
     (企微/钉钉/飞书)   │                  (防抖/去重)     ↕    ↕              (禅道/Gitee/...)
                        │                            LLM(Claude)  │
          Web 面板 ─────┤                                         │
         (Vue 3 SPA)    │                                         │
                        └── Relay Server ─────────────────────────┘
                           (公网中继，可选)
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
npm run dev   # Vite dev server，默认 http://localhost:5173
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENVORT_LLM_API_KEY` | LLM API Key（必填） | — |
| `OPENVORT_LLM_MODEL` | 模型名称 | `claude-sonnet-4-20250514` |
| `OPENVORT_LLM_PROVIDER` | 提供商（anthropic / openai_compatible） | `anthropic` |
| `OPENVORT_DATABASE_URL` | 数据库连接 | PostgreSQL（本地开发） |
| `OPENVORT_LOG_LEVEL` | 日志级别 | `INFO` |

完整配置参考 [`.env.example`](.env.example)。

## 项目结构

```
src/openvort/
├── core/           # 引擎核心（Agent Runtime / LLM Client / Session / Dispatcher）
├── plugin/         # 插件框架（BasePlugin / BaseTool / Registry / Loader）
├── plugins/        # 内置插件（禅道 / VortFlow / VortGit / 汇报 / 浏览器 / 定时任务 / 系统）
├── channels/       # IM 通道（企微 / 钉钉 / 飞书 / OpenClaw）
├── contacts/       # 通讯录（多平台身份映射）
├── auth/           # RBAC 权限
├── web/            # Web 面板后端（FastAPI + WebSocket + SSE）
├── db/             # 数据库（SQLAlchemy 2.0 async）
├── relay/          # Relay 公网中继
├── skill/          # Skill 知识注入
└── cli.py          # CLI 入口

web/                # 前端（Vue 3.5 + TypeScript 5.9 + Vite 7 + Tailwind CSS 4）
deploy/relay/       # Relay 中继独立部署（Node.js / Python）
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
