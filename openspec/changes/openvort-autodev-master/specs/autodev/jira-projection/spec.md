## Purpose

定义 Jira 工单如何单向投影为 OpenVort story 以充当派发队列：同步范围、字段与状态映射、覆盖规则、映射记录，以及 worker 结束后 story 的表内动作。Jira 是唯一真相；OpenVort MUST NOT 写 Jira。

## ADDED Requirements

### Requirement: 同步经 master 执行、按项目 JQL 增量
同步 SHALL 由一条 `action_type = autodev_sync` 的全局定时任务触发，对每个启用项目在 master 上执行 Jira 列表查询，查询 MUST 限定 `project = <项目 Jira key>` 并附项目配置的 JQL（默认 `updated >= -<M>d ORDER BY updated DESC`）。返回体 MUST 按「issue 列表，每项含 key 与 fields」解析；解析结果中任一条目无 key MUST 视为解析层错误并中止本项目本轮。

#### Scenario: 首次同步
- WHEN 项目从未同步过
- THEN 本轮 MUST 使用配置的首次窗口（默认 365 天）

#### Scenario: JQL 零命中
- WHEN 查询返回空列表
- THEN MUST 记录「零命中」并保留既有 story，MUST NOT 删除任何 story

### Requirement: 每张 Jira 单对应一条 story 与一条映射
同一项目内同一 Jira key MUST 只对应一条 story；映射 MUST 记录 Jira key 与上次同步时的 Jira 状态名。首次见到的 key MUST 创建 story（标题、描述、优先级、Jira 状态映射后的 state），已存在的 MUST 更新标题、描述、优先级。

#### Scenario: 重复同步
- WHEN 同一 key 连续同步两次
- THEN story 数量 MUST 不变

### Requirement: 状态映射只在 Jira 状态变化时覆盖
Jira 状态 → story 状态 MUST 按固定映射表 `STATUS_MAP` 转换（部署级常量，MUST NOT 作为项目属性）：`新增 / 补充说明 / 待确认 / 转支持确认中 → submitted`、`OPEN → in_progress`、`已修复 / 测试中 → testing`、`不处理 → rejected`、`CLOSE → done`。仅当本次 Jira 状态名与映射记录里的上次状态名**不同**时 MUST 覆盖 story 状态；相同时 MUST 保留 story 当前状态。映射表外的 Jira 状态 MUST 保留 story 状态并记录一次告警。

#### Scenario: 人在 OpenVort 侧推进到 dev_assign
- WHEN story 被人推到 `dev_assign` 且指派给 AI 员工，随后同步时 Jira 状态仍是「新增」
- THEN story MUST 仍为 `dev_assign`，队列不受影响

#### Scenario: Jira 侧打回 OPEN
- WHEN 上次同步 Jira 状态为「已修复」，本次为「OPEN」
- THEN story MUST 置为 `in_progress`

### Requirement: worker 结束后的 story 表内动作
运行记录收口时 MUST 按结果更新对应 story：`delivered → testing`、`failed / lost → dev_assign`、`verified / no_change` 不改状态；三种情况都 MUST 在 story 上追加一条系统评论，含退出码、含义、MR 链接（若有）与运行记录标识。

#### Scenario: worker 失败回到队列
- WHEN 运行以退出码 26（超时）收口
- THEN story MUST 回到 `dev_assign`，评论 MUST 含「超时被杀」；若熔断未触发，下一轮 MAY 再次派发

### Requirement: 不回写 Jira
本能力的任何动作 MUST NOT 对 Jira 发起写请求（评论、流转、指派、字段更新）。

#### Scenario: story 在 OpenVort 侧被改
- WHEN 用户在 OpenVort 改了 story 标题或状态
- THEN Jira 单 MUST 不变
