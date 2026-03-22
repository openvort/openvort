# Contributing to OpenVort

Thank you for your interest in contributing to OpenVort! This guide will help you get started.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use Docker Compose)
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/openvort/openvort.git
cd openvort

# Install backend in editable mode
pip install -e ".[dev]"

# Copy environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the dev server
openvort start --web

# Start the frontend dev server (in another terminal)
cd web
npm install
npm run dev
```

## How to Contribute

### Reporting Issues

- Search [existing issues](https://github.com/openvort/openvort/issues) first
- Use the issue template if available
- Include steps to reproduce, expected behavior, and actual behavior
- Include your environment info (OS, Python version, Node.js version)

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch from `main`: `git checkout -b feat/my-feature`
3. Make your changes
4. Run linting and tests:
   ```bash
   make lint
   make test
   ```
5. Commit with a clear message (see below)
6. Push to your fork and open a Pull Request

### Branch Naming

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feat/` | New feature | `feat/add-gitlab-plugin` |
| `fix/` | Bug fix | `fix/sse-reconnect` |
| `docs/` | Documentation | `docs/api-reference` |
| `refactor/` | Refactoring | `refactor/agent-runtime` |

### Commit Messages

We use conventional commit style in Chinese:

```
feat: 新增 GitLab 插件支持
fix: 修复 SSE 断连后无法重连的问题
docs: 更新 API 文档
refactor: 重构 Agent 运行时
```

## Code Style

### Backend (Python)

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Line length: 120 characters
- Target: Python 3.11+
- Run `ruff check .` and `ruff format .` before committing

### Frontend (TypeScript / Vue)

- Vue 3 Composition API with `<script setup lang="ts">`
- Tailwind CSS for styling
- Component library: shadcn-vue (Reka UI based)

## Project Structure

```
src/openvort/          # Backend Python package
├── channels/          # IM channel adapters (WeCom, DingTalk, Feishu)
├── config/            # Configuration & settings
├── core/              # Agent runtime, task runner, executors
├── db/                # Database models & migrations
├── plugins/           # Built-in plugins (Zentao, VortFlow, VortGit, etc.)
└── web/               # FastAPI web application

web/                   # Frontend Vue 3 SPA
├── src/components/    # Reusable components
├── src/views/         # Page views
└── src/api/           # API client
```

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0](LICENSE) license.
