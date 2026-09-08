# Design · OpenVort 接管 autodev master

## Context

见 `proposal.md · Why`。设计所依赖的现状（2026-09-07 服务器与源码实测）：

- worker 接口 = `worker.sh <ISSUE_KEY> --repo <主仓绝对路径>` + `AUTODEV_{IMAGE,MODEL,DELIVER,TIMEOUT,MEMORY,CPUS}` 环境变量；退出码契约 0/10/11/12/15/17/18/19/20–28/30–33；结束时打印 `[worker] 摘要 <run>/summary.json` 与 `[worker] 运行目录 <run>`；`summary.json` 含 ticket / branch / worktree / mr_url / image_id / exit_code / verdict。
- 密钥全部是 `/home/autodev` 下的只读文件（ADR-0002：不用 `-e`，openvort 容器挂着 docker.sock 能读 inspect）。每项目平台系统用户在 `<仓>/03_config/.env`，四键 `HCM_BASE_URL / HCM_USERNAME / HCM_PASSWORD / HCM_TOKEN`，最后一键由 hcmo 每日 cron 就地刷新。
- `usage-report.py` 按 run 目录时间窗归属 ocx 用量；当前 usage.jsonl 单文件共享挂载，**并发即串账**。
- 宿主 15.1 G，GitLab 常驻 4.0 G，worker 默认 4 G/个 → 现机器 2 并发是上限，3 并发需升配。
- OpenVort：`RemoteNode(docker)` 的指令 = `docker exec <cid> sh -c <cmd>`（镜像默认用户）；`Member.remote_node_id` 一对一绑节点；`ScheduleJob._execute_job` 只有 `agent_chat` 分支且硬要求 prompt；story 状态固定枚举；无 alembic，`create_all` + 自动补列；插件靠 entry point 加载，router 由宿主统一挂鉴权。
- kit `/req`：取单只读、不断言工单状态、无「AI 可接」标记、无工单级互斥；收口流转「已修复」并指派回建单人；「跨单不自动连跑，选单由人给」。

## Goals / Non-Goals

**Goals**
- worker 侧零改动地获得：队列、闸门、台账、用量、员工可查。
- 所有派发决策可用一条命令重跑复核，无 LLM 参与。
- 上百项目的形态下仍是一条定时任务、一个派发循环。

**Non-Goals**
- 不替代 `/req` 的任何阶段；不在 OpenVort 里写 Jira / GitLab。
- 不做 story → Jira 回写；不做需求方打回的专门再接逻辑。
- 不改 ocx 端口模型。

## Decisions

1. **master = 长驻容器 RemoteNode，openvort 只 `docker exec`**（而非宿主 systemd 调度器 / openvort 直接 `docker run` 重写 worker.sh）。master **全局唯一**，取自全局 AI 员工绑定的工作机（`Member.remote_node_id`），不是项目属性——一台机器服务所有项目，slot 因此按全局在跑数算。理由：复用现成执行器；worker.sh 已实测；宿主路径同名挂载后 worktree 的 `.git` 指针天然成立。代价：master 容器持有 docker.sock，与 openvort 主容器同级权限——本机 DooD 方案已知情接受。
2. **派发经 `ScheduleJob` + action 注册表**（而非插件自带 APScheduler）。`ACTION_HANDLERS[action_type] = async (job, config) -> str`，插件 activate 时注册；`_execute_job` 先查表，查到即跳过 prompt 校验与 Agent。既有 `agent_chat` 路径不变。
3. **一条全局派发任务，不按项目建任务**。处理器遍历 `enabled=true` 项目，按 `last_dispatched_at` 升序轮转；每轮每项目最多起 `max_starts`（默认 1）。同步任务同理一条全局 `autodev_sync`。
4. **队列 = story 投影**。可派条件：`FlowStory.project_id = 本项目 ∧ state = dev_assign ∧ assignee_id = 全局 AI 员工 ∧ 存在 jira 映射`。派出后 story → `in_progress`（OpenVort 表内写，不违反「Jira 唯一真相」）。worker 结束：`delivered → testing`、`failed/lost → dev_assign`、`verified/no_change` 不动，并加一条系统评论（退出码含义 + MR）。下一次同步若 Jira 状态变了，按映射表覆盖。
5. **Jira → story 状态映射表**（固定常量 `STATUS_MAP`，非项目属性）：`新增/补充说明/待确认 → submitted`、`OPEN → in_progress`、`已修复 → testing`、`不处理 → rejected`、`Closed/Resolved → done`。覆盖规则：仅当该单的 Jira 状态相对上次同步**发生变化**时覆盖 story 状态；否则保留 OpenVort 侧人推进的状态（含 `dev_assign`）。映射记录用 `FlowExternalMapping(local_type=story, adapter=jira, external_id=<KEY>, sync_cursor=<上次 Jira 状态名>)`。
6. **同步经 master 跑 `jira --json issue list -p KEY --jql <JQL> --max N`**，openvort 只解析 JSON（返回体是 issue 列表，`fields.status.name` 等），不在 openvort 里养第二个 Jira 客户端。默认 JQL：`updated >= -<M>d ORDER BY updated DESC`，首次 `M` 取大值全量。
7. **闸门六道全在 contract 纯函数里**：enabled · paused · 熔断（最近 N 次已结束运行全 failed）· slot（按节点：`running(node) < node.max_slots`，`max_slots` 是节点 config 参数）· 日上限（按项目计数，阈值 `DAILY_CAP` 是常量）· 同单互斥（同 key 有 running 记录不派）。熔断阈值同为常量 `FAILURE_THRESHOLD`。分支按「拿到了什么」封闭穷尽，理由不猜。
8. **worker 后台化与回收**：launch = `docker exec` 里 `nohup setsid bash -c '<env> worker.sh KEY --repo R > D/worker.log 2>&1; echo $? > D/rc' &`，立即返回；回收循环每 60 s 对 running 记录 `cat D/rc` + grep 摘要行 → 读 `summary.json` → `usage-report.py --ticket KEY --json` 取 `run == basename($RUN)` 那条；超过 9 h 无 rc 判 `lost`。openvort 重启不影响在跑的 worker，重启后从 DB 继续回收。
9. **密钥三层**：通用（Jira/GitLab/CodeBuddy/ocx）留宿主文件不动；每项目平台系统用户入 OpenVort（项目属性三字段 Fernet，复用 vortgit crypto key）；下发 = 派发前 `docker exec` 用 stdin 写 `<仓>/03_config/.env`，只替换三行、保留其余行（含 `HCM_TOKEN`）、内容相同不写、覆盖时记日志。不走 env。
10. **员工绑定 master 但受黑名单**：`node_tools._resolve_container` 后加判据——节点 config `autodev_master: true` 时，`node_shell` 命令匹配 `worker\.sh|(^|\s)docker\s|/home/autodev/\.|\.git-credentials|\.jira-cli|glab-cli|03_config/\.env` 即拒绝并记日志；`node_file_write` 对同一路径集拒绝；`node_file_read` 对凭据路径拒绝。规则优先闸门化，不靠 prompt。
11. **费用 = token × 固定价目表**（`MODEL_PRICES[模型] = (input, output)` 元每百万 token；模型不在表内则只报 token）。价目源：vault `codebuddy-本机模型价格-20260904.md`，取高峰价，不做峰谷切换。
12. **前端**：项目详情页加「自动交付」tab（配置表单 / 队列 / 运行记录 / 统计 / 立即派发 / 暂停恢复）；定时任务页不改，全局任务由插件首次激活时按需创建（禁用态），管理员在自动交付页一键启用。
13. **代码落点**：openvort 仓 `plugins/autodev/`（草稿已在盘上，按本设计改：候选源从 JQL 直查改为 story 队列；`max_slots` 从项目属性挪到节点 config；密钥字段与 `.env` 写入新增；黑名单新增）；master Dockerfile 放服务器 `/data/autodev/build/v4/Dockerfile.master`，openvort 仓只留使用说明。

14. **部署级常量收敛（2026-09-08 修订）**：worker 脚本 / 镜像 / 模型 / 派发根目录 / 用量脚本 / 超时 / 日上限 / 熔断阈值 / 模型单价 / Jira 状态映射，原设计里的项目属性一律改为 `contract.py` 常量，页面只读展示，`GET /api/autodev/global` 的 `fixed` 返回。理由：这些值全流水线一套，逐项目配置只产生漂移和「哪份是真的」；改动条件明确（换镜像 / 换模型 / 服务器布局变 / Jira 工作流改名），改一处常量比改 N 个项目行更可审。项目属性只剩：仓路径、Jira key、同步 JQL 与窗口、真交付开关、启用开关、平台系统用户、非密变量。
15. **master 不按项目绑定（2026-09-08 修订）**：项目表去掉 `master_node_id`，master = 全局 AI 员工的 `remote_node_id`。理由：AI 员工本来就绑一台工作机，让每个项目再选一次是同一事实的两处记录。

## Risks / Trade-offs

- [master 持 docker.sock，员工有 node_shell] → 黑名单零 LLM 判据 + 拒绝记日志；黑名单是可扩展起点不是完备集，`docs` 写明漏拦面。
- [并发下 usage 串账] → 前置任务改 worker.sh 为每轮独立 usage 文件（`usage-report.py` 旧形态已支持）；未改完前节点 `max_slots` 锁 1。
- [3 并发内存不足] → 节点 `max_slots` 默认 1，升配前手动最多 2；文档给出内存判据（可用 ≥ slots × 4 G + 1 G）。
- [Jira 状态映射覆盖人推进的 story] → 只在 Jira 状态变化时覆盖（决策 5）；测试覆盖「Jira 未变 + 人推进到 dev_assign」不被打回。
- [同一单被派发器与人手工 worker.sh 同时跑] → OpenVort 台账只管自己派的；人手工跑仍可能撞，文档写明「上 OpenVort 后不再手敲 worker.sh」。
- [`.env` 覆盖冲掉 hcmo 刷新的 token] → 只替换三行、逐行保留；测试覆盖 token 行保留。
- [`docker exec` 默认用户 ≠ 1001] → master 镜像 `USER autodev`；启动脚本断言 `id -u` = 1001。
- [openvort 重启期间 worker 结束] → rc 落文件，回收循环重启后照常读到。

## Migration Plan

1. 前置：合并 `send_instruction` 签名修复；服务器 worker.sh usage 每轮独立；建 `Dockerfile.master`、起 `autodev-master` 容器、登记节点（`config.container_id`、`autodev_master: true`、`max_slots: 1`）；vault 定调修订。
2. 部署 openvort 分支到服务器（`update.sh feat/autodev-master`），建表自动完成。
3. cpic 项目：填配置（仓路径 / Jira key / 平台系统用户）、`deliver=false`；启用同步任务，确认 story 投影正确（数量 = JQL 命中数）。
4. 指派 1 张 story 给 AI 员工 → 手动「立即派发」→ 回收得到 exit 15 与用量 → 员工能答出来。
5. 启用全局派发任务（间隔 5 min），跑 3 张仍为 `deliver=false`；再翻 `deliver=true` 跑 1 张真交付。
6. 回滚：禁用两条全局任务即停；删节点绑定不影响 Jira/GitLab（OpenVort 从不写它们）；`.env` 三行回滚 = 重新填写。

## Open Questions

- 升配到 32 G 的时点（不影响本设计，只影响 `max_slots` 取值）。
- 黑名单命中是否要通知管理员（一期只记日志）。
