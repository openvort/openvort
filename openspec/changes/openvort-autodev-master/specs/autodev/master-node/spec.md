## Purpose

定义 autodev 的 master 工作节点：一个由 OpenVort 登记与驱动的长驻容器，负责代 OpenVort 在宿主上起 worker、查 Jira、读用量；并约束 AI 员工在该节点上能做什么、密钥如何到达。

## ADDED Requirements

### Requirement: master 是 OpenVort 的 docker 工作节点
master SHALL 以 docker 类型工作节点登记，节点配置 MUST 含 `container_id`、`autodev_master: true`、`max_slots`（整数 ≥ 1）。OpenVort 对 master 的一切动作 MUST 经该节点的命令执行面完成，MUST NOT 直接操作宿主 docker。

#### Scenario: 节点缺 container_id
- WHEN master 节点配置里没有 `container_id`
- THEN 派发与同步 MUST 失败并返回「master 节点未配置 container_id」，不产生任何运行记录

#### Scenario: 节点不是 docker 类型
- WHEN master 节点 `node_type` 不是 `docker`
- THEN 派发与同步 MUST 拒绝并说明节点类型

### Requirement: master 由全局 AI 员工的绑定工作机确定
master 节点 MUST 取自全局 AI 员工（插件配置 `ai_member_id`）绑定的工作机，MUST NOT 作为项目属性逐项目配置——所有项目共用同一台 master，slot 也因此按全局在跑数计算。

#### Scenario: AI 员工未绑定工作机
- WHEN 全局 AI 员工的 `remote_node_id` 为空
- THEN 派发与同步 MUST 失败并指出该员工未绑定工作机，不产生任何运行记录

#### Scenario: 未配置全局 AI 员工
- WHEN 插件配置里没有 `ai_member_id`
- THEN 派发与同步 MUST 失败并提示先配置全局 AI 员工

### Requirement: master 容器以 worker 同一身份运行
master 容器内执行命令的用户 MUST 是 uid 1001（autodev），且 `/data/autodev` 与 `/home/autodev` MUST 以宿主同名绝对路径挂载。

#### Scenario: 身份不符
- WHEN master 内 `id -u` 不是 1001
- THEN worker.sh 预检以退出码 30 拒绝，OpenVort 运行记录 MUST 以 `failed` 收口并保留该退出码

### Requirement: 命令失败与空输出不同形
经 master 执行的命令 MUST 以退出码判成败：非零退出 MUST 抛错并带上 stderr/stdout 前 500 字；MUST NOT 把非零退出的空输出当作「无结果」。

#### Scenario: jira CLI 认证失败
- WHEN master 上 `jira --json issue list` 非零退出
- THEN 同步 MUST 报错并中止本项目本轮，MUST NOT 把 story 清空或标记为已同步

### Requirement: 密钥不经环境变量到达 master 或 worker
OpenVort MUST NOT 通过容器环境变量传递任何密钥；派发命令的环境变量 MUST 只含 `AUTODEV_*` 控制项与项目配置的非密变量。非密变量键名 MUST 匹配 `[A-Z_][A-Z0-9_]*`，且 MUST NOT 含 `TOKEN / SECRET / PASSWORD / PASSWD / APIKEY / API_KEY / CREDENTIAL` 子串，MUST NOT 以 `AUTODEV_` 开头。

#### Scenario: 项目配置里放了密钥样键
- WHEN 管理员在非密变量里填 `GITLAB_TOKEN`
- THEN 保存 MUST 被拒绝并指出键名

### Requirement: AI 员工在 master 上受命令黑名单约束
当员工绑定的节点配置 `autodev_master: true` 时，`node_shell` 的命令、`node_file_write` 的目标路径、`node_file_read` 的目标路径 MUST 先过黑名单；命中 MUST 拒绝执行、返回拒绝原因并记录日志。黑名单 MUST 至少覆盖：`worker.sh`、以 `docker` 开头的子命令、`/home/autodev/.` 下的隐藏目录与文件、`.git-credentials`、`.jira-cli`、`glab-cli`、`03_config/.env`。

#### Scenario: 员工被要求直接起 worker
- WHEN 用户在聊天里让员工「在工作机上跑 worker.sh TPYBX-1」
- THEN `node_shell` MUST 拒绝并说明「派发只经自动交付闸门」，MUST NOT 起任何容器

#### Scenario: 非 master 节点不受影响
- WHEN 员工绑定的节点没有 `autodev_master: true`
- THEN 黑名单 MUST 不生效，`node_shell` 行为与现状一致

#### Scenario: 普通数据处理命令放行
- WHEN 员工在 master 上执行 `python3 /data/autodev/bin/usage-report.py --json`
- THEN 命令 MUST 正常执行
