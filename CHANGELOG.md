# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-03-23

### Added

- MCP Server integration for Cursor and Claude Desktop
- Channel Bots: AI employees can operate as independent IM bots
- Knowledge base folder management with batch document operations
- Manual notification with customizable reminders and follow-up messages
- Plugin metadata extension API for richer plugin details
- Skills management and Extensions management pages

### Changed

- Reorganized menu structure with updated labels and paths

### Removed

- Removed unused VortEditor type declarations

[0.4.0]: https://github.com/openvort/openvort/releases/tag/v0.4.0

## [0.1.0] - 2026-03-17

### Added

- AI Agent runtime with Claude tool use agentic loop and multi-model failover
- AI Employee system with role-based Skill binding and scheduled tasks
- Async task execution decoupled from SSE, with background task progress and notification
- Multi-IM channel support: WeCom, DingTalk, Feishu, OpenClaw
- Web management panel (Vue 3 + FastAPI) with SSE streaming chat
- Plugin architecture with 10 built-in plugins:
  - Zentao integration
  - VortFlow agile workflow (projects, iterations, work items, test cases)
  - VortGit code repository management (GitHub, Gitee, GitLab)
  - Jenkins CI/CD
  - Knowledge base (RAG)
  - Report management
  - Scheduled tasks
  - Browser automation (Playwright)
  - System management
  - Contacts & directory
- Skill knowledge injection with 4-tier hierarchy (built-in / public / personal / marketplace)
- Extension marketplace with Bundle upload, PyPI packages, and CLI publishing
- RBAC 4-level permission system
- Docker sandbox for secure code execution
- Token encryption with Fernet
- Database migration support with Alembic
- Docker Compose deployment

[0.1.0]: https://github.com/openvort/openvort/releases/tag/v0.1.0
