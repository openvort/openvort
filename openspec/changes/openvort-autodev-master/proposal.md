# OpenVort 接管 autodev 流水线的 master

## Why

autodev 无人值守交付流水线的 worker（`docker run --rm` 一次性容器，容器内跑 `/req <单号>`）已在服务器上跑通真实工单，但 master 至今是「人手敲 `worker.sh <单号> --repo <仓>`」：没有队列、没有闸门、没有运行记录、每单用量只能事后跑脚本看。OpenVort 已经在同机运行且自带 AI 员工、工作项（story）、定时任务与工作节点四样基础设施，由它承担 master 是成本最低的一条路；但它当前一样都不支持这个方案——`ScheduleJob` 只认 `agent_chat`、项目上没有任何配置字段、`FlowExternalMapping` 有表无代码、docker 节点执行器还有一处签名不一致。

## What Changes

- **master 节点**：一个长驻容器（以 worker 镜像为基底 + docker CLI，uid 1001，挂 docker.sock 与 `/data/autodev`、`/home/autodev` 同路径）登记为 OpenVort 的 docker 类型工作节点；OpenVort 对它只做 `docker exec`。worker.sh 与 run-task.sh **一行不改**。
- **派发**：新增 `ScheduleJob` 的确定性 action 机制（非 `agent_chat` 的 action 走注册表里的处理器，不经 LLM）。一条**全局**派发任务遍历全部启用项目，按机械闸门起 worker：slot 按节点、日上限与熔断按项目、暂停、同单互斥、`AUTODEV_DELIVER` 开关；项目间按上次派发时间轮转。
- **派发源 = OpenVort story**：Jira 工单经 master 上的 `jira` CLI 单向投影为本项目 story（Jira 是唯一真相），映射存 `FlowExternalMapping(adapter=jira)`。「可派」= `state = dev_assign` 且 `assignee = 全局唯一的 AI 员工`，人把 story 指派给 AI 员工即为选单动作——保住 kit「选单由人给」的规则。
- **运行台账**：每次 worker 运行一条记录（单号、退出码及含义、结果四态、分支、MR、`usage-report.py` 归属的 token、按项目单价算的费用）；轮询回收，openvort 重启不丢在跑的 worker。
- **AI 员工**：只读工具 `autodev_status` / `autodev_runs`；员工绑定 master 节点，但 `node_shell` / `node_file_write` 对 master 节点拒绝 `worker.sh` / `docker ` / 凭据路径等模式，**零 LLM 判据**。
- **密钥**：Jira token / GitLab PAT / CodeBuddy / ocx 凭据保持宿主只读文件不变；**每项目**平台系统用户（`HCM_BASE_URL / HCM_USERNAME / HCM_PASSWORD`）入 OpenVort Fernet 存储，派发前写进该仓 `03_config/.env` 的这三行，保留 hcmo 自刷的 `HCM_TOKEN` 行，内容相同不写。
- **前置修复**：`DockerExecutor.send_instruction` 补 `extra_system_prompt`（现状对 docker 节点必 `TypeError`）；worker.sh 的 usage.jsonl 改回每轮独立文件（并发前提）。
- **不做**：Jira ↔ story 双向同步 · 平台配置同步（`platform-sync`）接入 master · ocx 端口多实例化 · 需求方打回后自动再接（靠「经办人 = AI 员工」信号与下一次同步自然进入队列，不做专门逻辑）。

## Capabilities

### New Capabilities

- `autodev/master-node`：master 工作节点的形态、命令执行面、员工侧命令黑名单与「密钥不经 env」约束。
- `autodev/dispatch`：派发队列语义、六道机械闸门、全局定时任务、项目轮转与互斥。
- `autodev/jira-projection`：Jira → story 单向投影的同步范围、状态映射、覆盖规则与 worker 结束后的 story 动作。
- `autodev/run-ledger`：运行记录、用量与费用归属、AI 员工查询工具与观测面。
- `autodev/project-secrets`：每项目平台系统用户凭据的存储、下发与写入语义。

### Modified Capabilities

（本仓 `openspec/specs/` 当前为空，无既有能力需修改。）

## Impact

- **openvort 仓**（自有 fork，分支 `feat/autodev-master`）：`core/services/schedule_service.py`（action 注册表）· `core/execution/docker_executor.py`（签名）· `core/execution/node_tools.py`（master 黑名单）· `db/engine.py`（建表导入）· `pyproject.toml`（entry point）· 新插件 `plugins/autodev/`（models / contract / service / router / tools / prompts）· 前端 `web/src/api/autodev.ts` + `views/vortflow/ProjectDetail.vue` 新 tab。
- **服务器 `/data/autodev`**：`build/v4/Dockerfile.master` 与 master 容器启动；`build/v4/worker.sh` usage 落点改动；master 节点登记。
- **kit 仓**：无代码改动；`docs/` 加一段「OpenVort master」指路。
- **vault**：`hcm-west-delivery.md` 定调修订（master/看板归 OpenVort，编排仍在 kit + Jira）；`openvort.md` 状态页；`autodev-pipeline` README 服务器实况更新。
- **既有行为**：`agent_chat` 定时任务不变；vortflow story 状态机不变（只是被投影写入）；worker 退出码契约不变。
