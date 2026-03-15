# OpenVort Web

OpenVort 管理面板前端，基于 Vue 3.5 + TypeScript 5.9 + Vite 7 + Tailwind CSS 4 构建。

## 技术栈

- **框架** — Vue 3.5（Composition API + `<script setup>`）
- **构建** — Vite 7
- **语言** — TypeScript 5.9
- **样式** — Tailwind CSS 4 + tw-animate-css
- **状态管理** — Pinia 3 + pinia-plugin-persistedstate
- **路由** — Vue Router 4
- **UI 组件** — Radix Vue / Reka UI + shadcn/vue 风格
- **图标** — Lucide Vue Next
- **图表** — ECharts 6
- **表单** — VeeValidate + Zod
- **HTTP** — Axios

## 开发

```bash
npm install
npm run dev        # 启动开发服务器（默认 http://localhost:5173）
npm run build      # 生产构建
npm run typecheck  # TypeScript 类型检查
```

## 页面结构

```
src/views/
├── chat/           # AI 聊天（SSE 流式 + 工具调用展示 + WebSocket 实时通知）
├── notifications/  # 通知中心（通知列表 / 筛选 / 批量已读）
├── dashboard/      # 仪表盘
├── overview/       # 总览（可定制 Widget）
├── vortflow/       # VortFlow 敏捷流程（Board/Stories/Tasks/Bugs/Milestones）
├── vortgit/        # VortGit 代码仓库（Repos/Providers/CodeTasks）
├── reports/        # 汇报管理
├── contacts/       # 通讯录
├── schedules/      # 定时任务
├── skills/         # Skill 知识管理
├── channels/       # IM 通道配置
├── plugins/        # 插件管理
├── webhooks/       # Webhook 管理
├── settings/       # 系统设置
├── agents/         # Agent 配置
├── login/          # 登录
└── profile/        # 个人设置（含通知偏好 — 声音/桌面/IM 延迟/DND）
```

## 核心 Composables

```
src/composables/
├── useWebSocket.ts      # 全局 WebSocket 连接（自动重连 + 消息分发）
└── useNotification.ts   # 通知能力（声音/Toast/桌面通知/Tab 标题）
```

## 状态管理（Pinia Stores）

```
src/stores/modules/
├── user.ts           # 用户认证与信息
├── app.ts            # 应用状态（侧边栏等）
├── notification.ts   # 未读计数 + 任务执行状态（全局实时）
├── activeTasks.ts    # AI 活跃任务追踪
├── config.ts         # 配置
├── plugin.ts         # 插件
├── vortflow.ts       # VortFlow
├── menu.ts           # 菜单
└── tabs.ts           # 标签页
```

## 与后端集成

开发模式下通过 Vite 代理转发 `/api` 和 `/ws` 请求到后端（默认 `http://localhost:8090`）。生产构建后静态文件由后端 FastAPI 直接托管。
