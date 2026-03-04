---
description: 在开始任何 OpenVort 相关开发任务前，优先读取 .cursor/skills 目录下的 SKILL.md 文件获取项目上下文和开发规范
---

# 使用 Cursor Skills 获取项目上下文

当处理 OpenVort 项目的任何开发任务时，优先读取以下 Cursor Skills 文件获取项目上下文、规范和最佳实践。

## 步骤

1. 读取项目概览 Skill，了解项目整体架构和技术栈：
   - 文件：`.cursor/skills/openvort-overview/SKILL.md`

2. 根据任务类型，读取对应的专项 Skill：
   - **前端开发**：`.cursor/skills/openvort-frontend/SKILL.md` — VortUI 组件用法、页面布局模式、CSS 约定、常见易错点
   - **架构变动**：`.cursor/skills/openvort-architecture/SKILL.md` — 架构文档同步更新规范
   - **后端重启**：`.cursor/skills/openvort-backend-restart/SKILL.md` — 后端服务重启流程
   - **聊天测试**：`.cursor/skills/openvort-chat-test/SKILL.md` — Web Chat 功能测试方法
   - **项目规划**：`.cursor/skills/openvort-plans/SKILL.md` — 迭代规划与任务拆分

3. 基于 Skill 中的规范和示例进行开发，确保代码风格一致。

## 注意事项

- Skills 目录位于 `.cursor/skills/`，每个子目录包含一个 `SKILL.md` 文件
- 前端开发务必参考 `openvort-frontend/SKILL.md` 中的组件 API、布局模式和常见易错点
- 修改架构时务必同步更新 `docs/architecture.md`
