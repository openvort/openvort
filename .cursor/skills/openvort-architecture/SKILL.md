---
name: openvort-architecture
description: OpenVort 项目架构变动时同步更新架构文档。新增模块、修改目录结构、调整技术栈或核心依赖时使用。
---

# OpenVort 架构维护 Skill

当对 OpenVort 项目进行架构变动时，必须同步更新架构文档。

## 触发条件

以下操作视为架构变动，需要触发本 Skill：

- 新增/删除/重命名 `src/openvort/` 下的模块目录
- 修改 `plugin/base.py` 中的基类接口（BasePlugin / BaseTool / BaseChannel）
- 修改 `plugin/registry.py` 或 `plugin/loader.py` 的插件发现/注册机制
- 修改 `core/agent.py` 的 agentic loop 流程
- 新增/删除 Channel 适配器（如新增钉钉、飞书）
- 新增/删除内置 Plugin（如新增 Gitee、Jenkins 插件）
- 修改 `cli.py` 的命令结构
- 修改 `pyproject.toml` 的 entry_points 组
- 新增核心概念或设计模式
- 技术栈变更（新增/替换依赖）

## 操作步骤

1. 读取架构文档：`/Users/yangqiang/Work/Projects/openvort/docs/architecture.md`
2. 根据本次变动，更新文档中对应的章节：
   - **技术栈**：依赖变更时更新表格
   - **核心架构图**：数据流变化时更新 ASCII 图
   - **分层说明**：目录结构变化时更新树形图
   - **核心概念**：接口/模式变化时更新代码示例和说明
   - **已实现功能**：新功能上线时在表格中添加行
   - **未来规划**：已实现的功能从规划移到已实现，新想法加入规划
   - **设计决策记录**：重大技术选型时新增决策条目
3. 确保文档与代码实际状态一致，不遗留过时信息

## 注意事项

- 不要删除已有的设计决策记录，它们是历史参考
- 未来规划中已实现的条目，移到「已实现功能」表并标记版本号
- 保持文档简洁，代码示例只展示接口签名，不贴完整实现
- 架构图使用 ASCII art，不依赖外部渲染工具
