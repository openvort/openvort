# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.7.1] - 2026-03-27

### Added

- **Developer mode** — `openvort start --dev` / `openvort restart --dev` skips IM channels, ASR/TTS, and heavy initialization for faster startup during development
- Dev mode banner shows actual backend port instead of `site_url`

### Improved

- Migrated to `@openvort/vort-ui` component library, reducing bundled component code

### Fixed

- Dev mode banner no longer misleads with `site_url` when the backend listens on a different port

## [0.7.0] - 2026-03-27

### Added

- **One-click Docker deployment** — Pre-built Docker images published to Docker Hub; two commands to deploy the full system
- **Auto-PostgreSQL** — `openvort start` automatically detects and starts a Docker PostgreSQL container when no local instance is running
- **Auto-Frontend** — Automatically downloads pre-built frontend assets from GitHub Release for `pip install` users
- **LLM graceful degradation** — Dashboard shows a configuration banner and chat returns a friendly message when no API Key is configured
- **Optional .env** — All settings have sensible defaults; AI configuration managed via Web panel
- AI Employee independent bot management: start and stop individual bots
- Test case, test plan, and test report management tools

### Improved

- Refactored dropdown menu and dialog components for better accessibility
- Enhanced internationalization support
- Optimized work item detail layout and progress bar styles
- Merged task/bug effort fields with batch name resolution

### Removed

- Deprecated `openvort init` command (all setup now handled by `openvort start`)

### Fixed

- Fixed build failure related to `@babel/runtime` dependency
- Fixed time handling to use UTC consistently
- Removed stale `alembic/` reference from Dockerfile
- Various stability improvements

## [0.6.0] - 2026-03-25

### Added

- Test report generation and detail view for test plans
- Test plan review workflow with pull request association
- Work item attachments: upload and manage files on work items
- Work item progress tracking with automatic calculation for stories and tasks
- Work item description templates for standardized creation
- Work item draft support: save and resume in-progress work items
- Work item type conversion between stories, bugs, and tasks
- Work item notification with customizable reminder messages
- Personal Access Token (PAT) management: create, list, and revoke tokens
- Knowledge base document detail page
- Batch property editing enhancements for work items

### Improved

- Plugin detail view now shows tool and prompt counts
- Extended work item status management with additional statuses and command fields
- Multi-status filtering for work item list queries
- Work item data source includes creation and update timestamps
- Table supports batch selection clear and refresh actions
- Comment updates now record event logs

### Fixed

- Work item data source filter logic error
- Various bug fixes and stability improvements

### Removed

- Legacy Zentao migration scripts
- TigShop documentation seed script

## [0.5.0] - 2026-03-24

### Added

- VortSketch AI prototype generator plugin
- Sprint and version management in VortFlow with story/bug association
- Work item deletion and duplication (stories, bugs, tasks)
- Task assignee field for team member assignment
- Estimated hours support for tasks
- Due date field for bug creation
- Sprint info display in bug list and detail views

### Improved

- AI chat float window supports drag-and-snap to screen corners
- MCP Server path trailing-slash compatibility
- Default password security: random initial password with mandatory change on first login

### Fixed

- bcrypt/passlib compatibility issue
- Docker and deployment configuration cleanup
- Various bug fixes and stability improvements

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

[0.6.0]: https://github.com/openvort/openvort/releases/tag/v0.6.0
[0.5.0]: https://github.com/openvort/openvort/releases/tag/v0.5.0
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

[0.5.0]: https://github.com/openvort/openvort/releases/tag/v0.5.0
[0.1.0]: https://github.com/openvort/openvort/releases/tag/v0.1.0
