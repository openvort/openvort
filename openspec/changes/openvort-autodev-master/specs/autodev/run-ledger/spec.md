## Purpose

定义每次 worker 运行的台账：记录什么、如何回收、用量与费用如何归属、AI 员工与管理员各能看到什么。台账是 OpenVort 侧关于「跑了什么、结果如何、花了多少」的唯一来源。

## ADDED Requirements

### Requirement: 每次运行一条记录
每次派发 MUST 产生一条运行记录，含：项目、Jira key、触发方式（manual / schedule）、状态（running / finished / lost）、退出码、结果（delivered / verified / no_change / failed）、退出码含义、分支、MR 链接、模型、镜像标识、worker 运行目录、开始与结束时间、错误文本。退出码到结果的映射 MUST 为：`0 → delivered`、`15 → verified`、`19 → no_change`、其余 → `failed`。退出码含义表 MUST 与 worker 契约同源。

#### Scenario: 未知退出码
- WHEN worker 以契约表外的退出码结束
- THEN 记录 MUST 标 `failed`，含义写「未知退出码 N」

### Requirement: 回收不依赖 OpenVort 进程存活
worker 的退出码与日志 MUST 落在 master 可读的文件上；回收 SHALL 由周期轮询完成（默认 60 s），OpenVort 重启后 MUST 从数据库中的 running 记录继续回收。超过配置时限（默认 9 小时）仍无退出码的记录 MUST 标 `lost`、结果 `failed`。

#### Scenario: openvort 在 worker 运行中重启
- WHEN worker 在 OpenVort 停机期间结束
- THEN OpenVort 启动后下一轮回收 MUST 把该记录收口为正确的退出码

#### Scenario: 摘要缺失
- WHEN 退出码已落但 worker 摘要文件不存在
- THEN 记录 MUST 仍以该退出码收口，并在错误文本里注明摘要缺失

### Requirement: 用量按运行归属、费用按固定价目表
收口时 MUST 读取 `usage-report.py` 的机读输出并取 `run` 等于本次运行目录名的那条，记录 input / output / total / cached token、调用次数、耗时。费用 = input 百万 token × 该模型 input 单价 + output 百万 token × 该模型 output 单价，单价取自固定价目表 `MODEL_PRICES`（键为模型名），MUST NOT 作为项目属性配置；模型不在价目表时费用为 0 且统计 MUST 标明「未配单价」。

#### Scenario: 模型不在价目表
- WHEN 运行记录的模型名不在 `MODEL_PRICES` 里
- THEN 费用 MUST 为 0，统计 MUST 标明未配单价，token 数照常记录

#### Scenario: 用量条目不存在
- WHEN 用量报告里没有本次运行目录名对应的条目
- THEN token 字段 MUST 为 0，错误文本 MUST 注明用量缺失，其余字段照常收口

### Requirement: 统计口径
项目统计 MUST 提供：窗口天数、运行数、running 数、各结果计数、涉及单数、`delivered` 单数、token 合计、费用合计、是否配价、当前闸门状态（允许数与理由）、队列长度。

#### Scenario: 队列长度
- WHEN 项目有 3 张 `dev_assign` 且指派给 AI 员工的 story，其中 1 张已有 running 记录
- THEN 队列长度 MUST 报 2，running MUST 报 1

### Requirement: AI 员工只读查询
AI 员工 MUST 拥有两个只读工具：项目状态（统计 + 队列长度）与运行记录列表（可按 KEY 过滤）。工具返回 MUST 只含记录里的字段，MUST NOT 含 master 内部路径；员工回答中的数字 MUST 来自工具返回。

#### Scenario: 问「今天做完几张」
- WHEN 用户问 AI 员工今天完成了多少张单
- THEN 员工 MUST 调用状态工具并按 `delivered` 单数作答，未配单价时 MUST 只报 token 不报金额

### Requirement: 管理员观测面
项目详情页 MUST 提供：配置表单、队列列表、运行记录表（含退出码含义与 MR 链接）、统计卡片、立即派发 / 暂停 / 恢复、启用或停用全局定时任务。配置写入 MUST 仅限管理员。

#### Scenario: 非管理员改配置
- WHEN 非管理员调用配置写入接口
- THEN MUST 返回 403
