## Purpose

定义 OpenVort 如何决定「现在给哪个项目的哪张单起一个 worker」：队列语义、六道机械闸门、全局定时任务的遍历与轮转、以及派发动作本身的可观测结果。派发决策 MUST 不经任何 LLM。

## ADDED Requirements

### Requirement: 队列由 story 投影定义
项目的派发队列 SHALL 是满足全部条件的 story 集合：属于本项目 · `state = dev_assign` · `assignee` 是全局配置的 AI 员工 · 存在 Jira 映射。队列 MUST 按优先级降序、创建时间升序排序。人把 story 指派给 AI 员工并置于 `dev_assign` 即为选单动作；系统 MUST NOT 自动把 story 指派给 AI 员工。

#### Scenario: story 指派给了人
- WHEN 某 story 处于 `dev_assign` 但 assignee 是真人成员
- THEN 它 MUST NOT 进入队列

#### Scenario: story 无 Jira 映射
- WHEN 某 story 手工创建、没有 Jira 映射
- THEN 它 MUST NOT 进入队列，派发器 MUST 在项目状态里列出「无映射被跳过」的数量

### Requirement: 六道闸门按结果分支封闭穷尽
派发前 MUST 依次判定并在任一不通过时停止、给出唯一理由：①项目未启用 ②派发已暂停 ③熔断（该项目最近 N 次已结束运行全部 `failed`，N = 固定常量 `FAILURE_THRESHOLD`，0 表示关闭）④节点 slot（master 上 running 记录数 ≥ 节点 `max_slots`）⑤项目日上限（当日已起运行数 ≥ 固定常量 `DAILY_CAP`）⑥同单互斥（同一 Jira key 已有 running 记录）。日上限与熔断阈值是部署级常量，MUST NOT 作为项目属性。通过时允许起的数量 = min(空余 slot, 日上限余量, 本轮上限)。

#### Scenario: slot 由节点共享
- WHEN 两个项目（必然共用同一 master），节点 `max_slots = 1`，项目 A 有一条 running
- THEN 项目 B 本轮 MUST 不派发，理由为 slot 已满

#### Scenario: 熔断只看连续窗口
- WHEN `FAILURE_THRESHOLD = 3`，最近三次结果为 failed / delivered / failed
- THEN MUST 不触发熔断

#### Scenario: 同单互斥
- WHEN 队列首位 story 对应的 Jira key 已有 running 记录
- THEN MUST 跳过它取下一张，且 MUST NOT 为它再起运行

### Requirement: 一条全局派发任务遍历全部项目
派发 SHALL 由一条 `action_type = autodev_dispatch` 的定时任务触发，处理器 MUST 遍历全部 `enabled` 项目，按 `last_dispatched_at` 升序轮转，每项目每轮最多起 `max_starts`（默认 1）。处理器 MUST 是确定性代码，MUST NOT 调用 Agent；执行结果文本 MUST 列出每个项目「已派发 KEY…」或「未派发：理由」。

#### Scenario: 定时任务无 prompt
- WHEN 定时任务 `action_type = autodev_dispatch` 且 `action_config` 无 `prompt`
- THEN 任务 MUST 正常执行，MUST NOT 因缺 prompt 报错

#### Scenario: 处理器抛错
- WHEN 处理器执行中抛出异常
- THEN 任务记录 MUST 标 `failed` 并保存异常文本，其他 `agent_chat` 任务不受影响

#### Scenario: 轮转公平
- WHEN 三个项目都有队列且节点只剩一个 slot
- THEN 本轮 MUST 派给 `last_dispatched_at` 最早的项目

### Requirement: 派发动作与开关
起 worker MUST 以 `worker.sh <KEY> --repo <项目仓路径>` 的形式在 master 上后台执行，环境 MUST 含 `AUTODEV_IMAGE / AUTODEV_MODEL / AUTODEV_TIMEOUT / AUTODEV_DELIVER`（项目 `deliver=false` 时为 0）。派发 MUST 先落运行记录再起容器；起容器失败时该记录 MUST 以 `failed` 收口并写明启动失败原因。派出后对应 story MUST 置为 `in_progress`。

#### Scenario: deliver 关闭
- WHEN 项目 `deliver = false`
- THEN worker MUST 以 `AUTODEV_DELIVER=0` 运行，成功结果为退出码 15、结果 `verified`

#### Scenario: 同一派发目录不二次点火
- WHEN 同一运行的启动命令被重复执行
- THEN 第二次 MUST 因退出码文件已存在而拒绝

### Requirement: 手动派发与暂停
管理员 MUST 能对项目执行：立即派发（可指定 KEY，仍过全部闸门）、暂停、恢复。AI 员工 MUST NOT 拥有派发、暂停、改配置的工具。

#### Scenario: 指定 KEY 已在运行
- WHEN 管理员手动派发一个已有 running 记录的 KEY
- THEN MUST 拒绝并说明该单已在运行
