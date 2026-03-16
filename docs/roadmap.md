# OpenVort 未来发展规划

> 版本: 0.1.0 | 最后更新: 2026-03-16

本文档梳理 OpenVort 的未来发展方向、待改进领域和优化计划。分为近期改进（v0.2 - v0.3）、中期规划（v0.4 - v0.6）和长期愿景三个阶段。

---

## 一、近期改进（v0.2 - v0.3）

### 1.1 代码质量与工程化

#### 大文件拆分

当前多个核心文件行数过大，严重影响可维护性：

| 文件 | 行数 | 拆分方案 |
|------|------|---------|
| `plugins/vortflow/router.py` | 2179 | 按实体拆分: stories.py / tasks.py / bugs.py / iterations.py / versions.py |
| `cli.py` | 2210 | 按命令组拆分: server.py / user.py / plugin.py / data.py |
| `core/agent.py` | 1214 | 分离 tool dispatch、消息处理、usage tracking |
| `web/routers/chat.py` | 1031 | 分离会话管理、消息处理、SSE 流 |
| `core/llm.py` | 812 | 分离各 Provider adapter 为独立文件 |
| `WorkItemTable.vue` | 3127 | 继续拆分 request/crud/detail 逻辑 |
| `chat/Index.vue` | 2413 | 分离会话列表、消息面板、输入框、设置面板 |
| `contacts/Index.vue` | 2291 | 分离联系人列表、详情面板、部门树 |
| `api/index.ts` | 1910 | 按模块拆分: auth.ts / chat.ts / vortflow.ts / vortgit.ts |

#### 错误处理优化

- 消除后端 57+ 处 `except Exception: pass` 静默吞错，改为 `log.debug` / `log.warning`
- 消除前端 30+ 处空 `catch {}` 块，添加 `console.warn` 或 `message.error`
- 高发文件优先: `browser/plugin.py`(8 处)、`knowledge.py`(6 处)、`schedule_service.py`(4 处)

#### TypeScript 类型安全

- 消除 400+ 处 `any` 类型，定义 API 响应 interface
- 开启 `noUnusedLocals` 和 `noUnusedParameters` 严格检查
- 典型改进: `(res as any)?.items` → 定义泛型 API 响应类型

#### 依赖治理

- 后端依赖添加版本上界（如 `anthropic>=0.40,<1.0`、`fastapi>=0.115,<1.0`）
- 前端统一 headless UI 库（`radix-vue` + `reka-ui` 二选一，减少约 200KB 冗余）
- ECharts 按需引入（全量 ~800KB，仅 2 个页面使用）
- 清理未使用依赖（如 `python-jose` 已声明但未使用）

### 1.2 测试覆盖

当前约 230 个 Python 源文件，仅 9 个测试文件；前端 0 个测试。

#### 优先补充

1. **核心 API 集成测试**：auth / chat / vortflow CRUD（FastAPI TestClient）
2. **Agent Runtime 单元测试**：agentic loop、thinking 支持、usage 追踪
3. **状态机流转测试**：Story / Task / Bug 各状态转换路径
4. **LLM Provider 测试**：mock 各 Provider 响应，验证 Failover 逻辑
5. **前端组件测试**：关键业务组件的 Vitest 测试

#### CI/CD 集成

- 添加 GitHub Actions CI 流水线（lint + test + coverage）
- 测试覆盖率报告集成
- 前端 ESLint + TypeScript 严格检查

### 1.3 安全加固

| 问题 | 方案 | 优先级 |
|------|------|--------|
| JWT 签名密钥与默认密码耦合 | JWT_SECRET 独立配置，不依赖 default_password | P0 |
| 登录无暴力破解防护 | 添加 IP 级 rate limiting（slowapi） | P1 |
| CORS `allow_origins=["*"]` | 提供 `OPENVORT_WEB_CORS_ORIGINS` 配置项 | P1 |
| 备份下载路径穿越风险 | `path.resolve().is_relative_to(backup_dir)` 检查 | P1 |
| Token 通过 URL query 参数传递 | SSE/备份下载改用 header 或 POST body 传递 | P2 |

### 1.4 功能补全

| 功能 | 现状 | 目标 |
|------|------|------|
| 评论系统前端对接 | 后端 API 已完成，前端仍用组件内 reactive | 对接后端 API，支持 @mentions |
| 工作日志 | WorkItemDetail 中仅占位文字 | 支持工时记录和工作日志 |
| 关联测试用例 | Tab 空壳 | 对接测试管理或提供基础用例管理 |
| 视频消息处理 | 按钮可点但无实际处理 | 实现或暂时隐藏入口 |
| StoryList 与 WorkItemTable 重复 | 两套独立需求管理页面 | 统一为一套实现 |

---

## 二、中期规划（v0.4 - v0.6）

### 2.1 多模型与 AI 能力增强

#### MCP (Model Context Protocol) 支持

- 接入 MCP 协议，让 Agent 可使用外部 MCP Server 提供的工具
- 支持自定义 MCP Server 注册
- Agent 工具集从"内置插件"扩展到"内置 + MCP"双来源

#### 模型能力扩展

- 支持更多 LLM Provider：Google Gemini、Mistral、本地部署模型（Ollama / vLLM）
- 多模型协作：不同任务阶段使用不同模型（如规划用强模型、执行用快模型）
- 模型评估框架：自动对比不同模型在特定任务上的表现

#### Agent 能力进化

- **长期记忆**：跨会话的用户偏好和项目知识持久化
- **自主规划**：复杂任务自动分解为子任务，顺序执行
- **多 Agent 协作**：多个 AI 员工之间自动协调（现有 session_tools 的深化）
- **反思与自纠**：执行后自动评估结果质量，不满意时重试

### 2.2 VortFlow 深化

#### 敏捷看板增强

- 看板拖拽排序（优先级调整）
- 泳道视图（按成员/优先级/标签分组）
- WIP 限制（在制品数量上限告警）
- 燃尽图和速度趋势图
- Sprint 回顾报告自动生成

#### 项目管理增强

- 甘特图视图
- 关键路径分析
- 资源分配视图（团队工作负载一览）
- 自定义字段（用户可为工作项添加自定义属性）
- 工作项模板（常用需求/任务/缺陷模板）

#### 外部系统双向同步

- Jira 双向同步（ExternalMapping 已预留接口）
- Zentao 双向同步增强（从只读查询到双向推送）
- Linear / Asana 适配器

### 2.3 VortGit 扩展

#### 平台覆盖

- GitHub 完整适配（已有 Webhook，补充 Provider API）
- GitLab 完整适配
- Gitee 增强（PR Review / Issue 管理）

#### 代码审查

- AI 自动 Code Review（PR 提交后触发 Agent 审查）
- Review 评论自动生成
- 代码质量评分
- 与 VortFlow 工作项自动关联

#### DevOps 闭环

- PR 合并后自动触发 Jenkins 构建
- 构建结果自动回写到 VortFlow 任务状态
- 部署后自动通知相关人员

### 2.4 知识库增强

#### 数据源扩展

- 网页抓取和自动更新
- Confluence / Notion 同步
- API 文档自动导入（Swagger/OpenAPI）
- 代码仓库文档自动索引

#### 检索增强

- Hybrid Search（向量 + 关键词混合检索）
- 知识图谱构建和关联推理
- 多轮追问上下文感知
- 知识库分类和权限控制

#### 交互增强

- 知识库对话（专属 RAG 聊天窗口）
- 文档在线预览和标注
- 自动过期和更新提醒

### 2.5 扩展市场

- Skill 市场：社区共享 Skill 模板
- Plugin 市场：第三方插件分发（PyPI + 前端 Bundle）
- 一键安装/更新/卸载
- 评分和评论系统
- 版本管理和兼容性检查

---

## 三、长期愿景（v1.0+）

### 3.1 多租户与 SaaS

- 多组织隔离（数据、配置、Agent 实例独立）
- 租户级资源配额管理
- 计费和用量统计
- SSO 集成（SAML / OIDC）

### 3.2 高可用与水平扩展

- 多实例部署和负载均衡
- 会话状态分布式存储（Redis / 分布式缓存）
- Agent 任务队列化（Celery / RabbitMQ），支持水平扩展
- 数据库读写分离和分片

### 3.3 国际化

- vue-i18n 集成，前端全面国际化
- 后端消息模板多语言支持
- 时区和日期格式本地化
- 英文 / 日文 / 韩文等语言包

### 3.4 可观测性

- OpenTelemetry 集成（Tracing + Metrics + Logging）
- Agent 执行链路追踪（每轮 tool use 的耗时和结果可视化）
- LLM 调用成本仪表盘
- Token 用量趋势分析和预算告警
- 插件健康度监控

### 3.5 移动端

- 响应式 Web 适配（当前部分页面移动端体验不佳）
- PWA 支持（离线访问、推送通知）
- 移动端专属交互优化（语音输入为主、快捷操作）

### 3.6 工作流自动化引擎

- 可视化工作流编辑器（类 n8n / Zapier）
- 条件分支、循环、并行执行
- 事件触发器（Webhook / 定时 / 状态变更 / IM 消息）
- 与现有插件系统深度整合
- 工作流模板市场

### 3.7 AI 原生 IDE 集成

- VS Code / Cursor 插件：在 IDE 中直接对接 OpenVort
- 任务上下文自动注入 IDE（打开相关代码文件、设置工作分支）
- 编码进度实时同步到 VortFlow
- PR 提交后自动更新任务状态

---

## 四、待优化领域

### 4.1 性能优化

| 领域 | 现状 | 优化方案 |
|------|------|---------|
| **会话加载** | 大量历史消息从 DB 加载 | 分页加载 + 滚动懒加载 |
| **知识库检索** | 全表向量距离计算 | IVFFlat / HNSW 索引优化 |
| **前端首屏** | ECharts 全量导入 ~800KB | 按需引入，路由级代码分割 |
| **IM 消息处理** | 同步等待 Agent 响应 | 消息队列异步处理，支持水平扩展 |
| **插件加载** | 启动时全量加载所有插件 | 按需延迟加载，减少启动时间 |

### 4.2 开发体验

| 领域 | 现状 | 优化方案 |
|------|------|---------|
| **API 文档** | 仅 FastAPI 自动生成 | 独立 API 文档站点（含使用示例） |
| **插件开发** | 无脚手架 | `openvort create-plugin` 命令生成模板 |
| **前端组件文档** | 无 | Storybook 或 VitePress 组件文档 |
| **调试工具** | CLI `agent chat` 基础调试 | 可视化调试面板（查看 prompt、tool call、token 用量） |
| **数据库迁移** | `db/engine.py` 含 400 行手工 DDL | 全面迁移到 Alembic |

### 4.3 用户体验

| 领域 | 现状 | 优化方案 |
|------|------|---------|
| **首次使用引导** | CLI `openvort init` + Web 启动向导 | 更完善的交互式引导流程，含示例数据 |
| **错误提示** | 部分场景 generic error | 细化错误消息，提供修复建议 |
| **搜索体验** | 各模块独立搜索 | 全局搜索（跨模块、跨工作项） |
| **批量操作** | 基础多选 | 增强批量编辑（批量修改状态/负责人/迭代等） |
| **键盘快捷键** | 几乎无 | 常用操作快捷键支持 |
| **可访问性** | 20+ 处 `<img>` 缺少 alt，无 ARIA 标注 | 补充语义化标签和 ARIA |

### 4.4 文档完善

| 文档 | 现状 | 目标 |
|------|------|------|
| **贡献指南** | 无 | CONTRIBUTING.md（代码规范、PR 流程、开发环境搭建） |
| **变更日志** | 无 | CHANGELOG.md（SemVer 规范，自动生成） |
| **部署指南** | README 简要说明 | 独立部署文档（Docker / 源码 / 各 IM 平台配置） |
| **API 参考** | FastAPI 自动生成 | 独立 API 文档站点 + SDK |
| **插件开发指南** | 无 | 完整的插件开发教程 + 示例 |
| **源码注释** | 覆盖率约 10% | 核心模块 docstring 覆盖率提升到 80%+ |
| **许可证头** | 源码文件无许可证头 | 批量添加 AGPL-3.0 许可证头 |

---

## 五、技术债务清单

| 编号 | 问题 | 影响 | 优先级 |
|------|------|------|--------|
| TD-01 | `db/engine.py` 含约 400 行手工 DDL migration | 新增表结构需手动更新两处 | High |
| TD-02 | `python-jose` 依赖已声明但未使用 | 依赖冗余 | Low |
| TD-03 | `StoryList.vue` 与 `WorkItemTable.vue` 功能重复 | 维护成本翻倍 | High |
| TD-04 | 前端 `noUnusedLocals` / `noUnusedParameters` 为 false | 死代码积累 | Medium |
| TD-05 | 后端 57+ 处静默异常吞没 | 生产环境难以定位问题 | High |
| TD-06 | 前端 400+ 处 `any` 类型 | 类型安全缺失，重构风险高 | Medium |
| TD-07 | `radix-vue` + `reka-ui` 双重 headless UI 依赖 | 约 200KB 冗余 | Medium |
| TD-08 | `WorkItemCreate.vue` 含硬编码 mock 数据 | 开源后容易被质疑代码质量 | High |
| TD-09 | ImportRecordDialog 记录硬编码 | 导入历史为静态数组 | Medium |
| TD-10 | 手写 JWT 实现未使用 python-jose | 安全隐患 | High |

---

## 六、社区建设

### 6.1 开源运营

- **GitHub Discussions** 启用：问答 / 功能请求 / 最佳实践分享
- **Issue 模板**：Bug Report / Feature Request / Question
- **PR 模板**：变更说明 / 测试计划 / 截图
- **Code of Conduct**：社区行为准则
- **Good First Issues**：标记适合新贡献者的入门任务

### 6.2 生态建设

- **官方文档站点**：VitePress 搭建，含安装 / 配置 / 插件开发 / API 参考
- **视频教程**：从安装到高级使用的系列教程
- **示例插件仓库**：提供 2-3 个示例插件作为开发参考
- **官方 Discord / 微信社区**：实时交流渠道

### 6.3 发布节奏

- **月度小版本**：bug 修复 + 小功能迭代
- **季度大版本**：重大功能发布
- **LTS 版本**：每年一个长期支持版本

---

*本文档是动态文档，随项目进展持续更新。欢迎通过 GitHub Issues 提交功能建议和改进意见。*
