# OpenVort 开源发布审计报告

> 生成时间: 2026-03-15
> 范围: 全项目（后端 Python + 前端 Vue/TypeScript）

## 一、安全问题

### Critical

| # | 问题 | 文件 | 说明 | 建议 |
|---|------|------|------|------|
| S1 | JWT 签名密钥从默认密码派生 | `web/auth.py:20-24` | 所有未改默认密码的实例共享同一 JWT 签名，攻击者可伪造 token | JWT_SECRET 独立配置，不依赖 default_password |
| S2 | 手写 JWT 实现 | `web/auth.py:38-59` | 依赖 `python-jose` 已声明但未使用，手写 JWT 更易出漏洞 | 使用 `python-jose` 或 `PyJWT` 标准库 |

### High

| # | 问题 | 文件 | 建议 |
|---|------|------|------|
| S3 | 登录无暴力破解防护 | `web/routers/auth.py` | 添加 IP 级 rate limiting（如 `slowapi`） |
| S4 | CORS `allow_origins=["*"]` | `web/app.py:48` | 提供 `OPENVORT_WEB_CORS_ORIGINS` 配置项 |
| S5 | 备份下载路径穿越风险 | `core/updater.py:197-202` | 添加 `path.resolve().is_relative_to(backup_dir)` 检查 |

### Medium

| # | 问题 | 文件 | 建议 |
|---|------|------|------|
| S6 | 文件上传扩展名取自客户端文件名 | `web/routers/me.py:261` | 扩展名从 content_type 映射获取 |
| S7 | 默认密码 `openvort` 硬编码 | `config/settings.py:212` | 文档中强调生产环境必须修改 |
| S8 | Token 通过 URL query 参数传递 | 前端 SSE/备份下载 | URL token 可能泄露到日志/浏览器历史 |

### 开源前必做

1. 使用 BFG Repo Cleaner 清除 git 历史中的 `.env` 真实凭证
2. 确认 `.env` 在 `.gitignore` 中且从未提交

---

## 二、大文件需拆分

### 后端（Python，>500 行）

| 文件 | 行数 | 优先级 | 拆分建议 |
|------|------|--------|----------|
| `plugins/vortflow/router.py` | 2179 | High | 按实体拆分: stories.py, tasks.py, bugs.py, iterations.py, versions.py, milestones.py, views.py, comments.py |
| `cli.py` | 1750 | High | 按命令组拆分: server.py, user.py, plugin.py, data.py |
| `core/agent.py` | 1214 | High | 分离 tool dispatch、消息处理、usage tracking |
| `channels/wecom/channel.py` | 981 | Medium | 分离消息解析、API 调用、Bot WebSocket |
| `plugins/vortgit/tools/coding.py` | 923 | Medium | 按功能拆分 |
| `channels/dingtalk/channel.py` | 910 | Medium | 同 wecom 模式 |
| `web/routers/chat.py` | 848 | Medium | 分离会话管理、消息、SSE 流 |
| `core/llm.py` | 812 | Medium | 分离 provider adapter |
| `db/engine.py` | 554 | Medium | DDL 迁移到 Alembic migration 文件 |

### 前端（Vue/TS，>1000 行）

| 文件 | 行数 | 优先级 | 拆分建议 |
|------|------|--------|----------|
| `views/vortflow/WorkItemTable.vue` | 2806 | High | 已提取 useWorkItemInlineEdit.ts，还需继续拆分 request/crud/detail 逻辑 |
| `views/chat/Index.vue` | 2413 | High | 分离会话列表、消息面板、输入框、设置面板 |
| `views/contacts/Index.vue` | 2291 | High | 分离联系人列表、详情面板、部门树 |
| `components/vort/table/Table.vue` | 2065 | Medium | 基础组件可接受但仍偏大 |
| `api/index.ts` | 1910 | High | 按模块拆分: auth.ts, chat.ts, vortflow.ts, vortgit.ts 等 |
| `work-item/WorkItemDetail.vue` | 1574 | Medium | 分离评论面板、日志面板、属性编辑 |
| `pro-table/ProTable.vue` | 1525 | Medium | 分离排序/筛选/列管理为 composable |
| `work-item/WorkItemCreate.vue` | 1298 | Medium | 分离表单校验、项目/迭代选择逻辑 |

---

## 三、功能缺失与占位

### P0 -- 阻塞开源

| 问题 | 文件 | 说明 |
|------|------|------|
| `__CONTINUE_HERE__` 标记 | `dashboard/Index.vue:30` | 明确的开发中标记 |
| 视频上传 `/* TODO */` | `chat/Index.vue:847` | 按钮可点但无实际处理 |
| `// TODO: 调用API创建` | `useBugTrackingState.ts:450` | 缺陷创建未接入后端 |
| 硬编码 mock 数据 | `WorkItemCreate.vue:112-132` | VortMall/Sprint 1/v1.0.0 等示例值 |

### P1 -- 重要

| 问题 | 说明 |
|------|------|
| 评论前端未对接 API | D1 后端已完成，前端 WorkItemDetail 仍用组件内 reactive 存储 |
| 工作日志/关联测试用例 tab 为空壳 | WorkItemDetail 中仅占位文字 |
| StoryList.vue 与 WorkItemTable 功能重复 | 两套独立的需求管理页面 |
| ImportRecordDialog 记录硬编码 | 导入历史为静态数组 |

---

## 四、代码质量

### 错误处理

- **57+ 处** `except Exception: pass` 静默吞错（后端）
- **30+ 处** 空 `catch {}` 块（前端）
- 高发文件: `browser/plugin.py`(8), `knowledge.py`(6), `schedule_service.py`(4)
- **建议**: 至少添加 `log.debug` / `console.warn`

### TypeScript 类型安全

- **400+ 处** 使用 `any` 类型
- 典型模式: `(res as any)?.items` -- 缺少 API 响应类型定义
- `noUnusedLocals` 和 `noUnusedParameters` 均为 `false`
- **建议**: 定义 API 响应 interface，逐步消除 `any`

### 冗余/重复代码

| 问题 | 涉及文件 |
|------|----------|
| `StoryList.vue` 与 `WorkItemTable.vue` 功能重复 | 两套独立的需求 CRUD + 行内编辑 |
| `radix-vue` + `reka-ui` 双重 headless UI 依赖 | package.json |
| `python-jose` 依赖已声明但未使用 | pyproject.toml |
| `db/engine.py` 含约 400 行手工 DDL migration | 应使用 Alembic |

---

## 五、测试覆盖

### 现状

- 约 **230 个** Python 源文件，仅 **9 个** 测试文件
- 前端 **0 个** 测试文件
- 无 CI/CD 配置中的测试覆盖率报告

### 关键缺失

- 无 API 端点（FastAPI TestClient）测试
- 无认证/授权测试
- 无数据库 model 测试
- 无 VortFlow 业务逻辑测试
- 无前端组件单元测试
- 无 E2E 测试

### 建议优先补充

1. 核心 API 端点的集成测试（auth, chat, vortflow CRUD）
2. Agent Runtime 的单元测试
3. 状态机流转的单元测试
4. 前端关键组件的 Vitest 测试

---

## 六、依赖与构建

### 后端

- 所有依赖仅指定 `>=` 最低版本，无上界限制
- **建议**: 至少 `anthropic>=0.40,<1.0`、`fastapi>=0.115,<1.0`
- `psycopg2-binary` 不建议用于生产（但开源降低安装门槛可接受）
- 无 `requirements.txt` lock 文件（仅 pyproject.toml）

### 前端

- `echarts` 全量导入（~800KB），仅用于 2 个页面
- `radix-vue` + `reka-ui` 功能重叠（~200KB 冗余）
- `pinyin-pro`（~150KB）仅 2 处使用
- **建议**: echarts 按需引入；统一 headless UI 库

---

## 七、可访问性与国际化

### 可访问性

- **20+ 处** `<img>` 缺少 `alt` 属性
- 业务页面几乎无 ARIA 标注
- 对话框缺少 focus trap
- 列表缺少键盘选择支持

### 国际化

- **无 vue-i18n**，业务层文本全部硬编码中文
- 底层 Vort 组件库有基础 locale（zh-CN/en-US）
- **建议**: README 声明当前仅支持中文，后续可接入 vue-i18n

---

## 八、文档

### 已有

- `README.md` -- 项目介绍和安装说明
- `docs/architecture.md` -- 架构文档
- `.env.example` -- 环境变量模板
- `LICENSE` -- AGPL-3.0

### 缺失

- API 文档（Swagger/ReDoc 已通过 FastAPI 自动生成，但未有独立文档）
- 贡献指南 (`CONTRIBUTING.md`)
- 变更日志 (`CHANGELOG.md`)
- 源码文件许可证头
- 后端 docstring 覆盖率仅约 10%

---

## 九、优先级排序

### P0 -- 开源前必须修复

1. 清除 git 历史中的凭证
2. JWT 签名密钥与默认密码解耦
3. 移除 `__CONTINUE_HERE__` 标记
4. 移除/替换 `WorkItemCreate.vue` 中硬编码 mock 数据
5. 视频上传 TODO 改为隐藏按钮或实现功能
6. 添加 `CONTRIBUTING.md`
7. 添加 `CHANGELOG.md`

### P1 -- 开源后尽快完成

1. 拆分 3 个 2000+ 行巨型后端文件
2. 拆分 3 个 2000+ 行巨型前端组件
3. 添加核心 API 集成测试
4. 收紧 CORS 配置
5. 添加登录 rate limiting
6. 前端评论功能对接后端 API
7. 统一 headless UI 依赖
8. 依赖版本约束添加上界

### P2 -- 持续改进

1. 消除 400+ 处 `any` 类型
2. 处理 57+ 处 `except Exception: pass`
3. 提升 docstring 覆盖率
4. 数据库迁移从手工 DDL 迁移到 Alembic
5. echarts 按需引入
6. 补充 `<img alt>` 属性
7. 清理 `StoryList.vue` 与 `WorkItemTable.vue` 重复代码
