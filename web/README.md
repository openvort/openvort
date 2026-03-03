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
├── chat/           # AI 聊天（SSE 流式 + 工具调用展示）
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
└── profile/        # 个人设置
```

## 与后端集成

开发模式下通过 Vite 代理转发 `/api` 和 `/ws` 请求到后端（默认 `http://localhost:8090`）。生产构建后静态文件由后端 FastAPI 直接托管。
