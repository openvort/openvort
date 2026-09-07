# AutoDev 自动交付插件

OpenVort 承担 autodev 无人值守交付流水线的 **master**：把 Jira 工单投影成 story 作派发队列、按机械闸门在 master 工作机上起 worker、回收每次运行的结果与用量、让 AI 员工能查。worker 本身（`worker.sh` + `autodev-worker` 镜像 + `/req` skill）不在本仓，一行不改。

设计与规格：`openspec/changes/openvort-autodev-master/`。

## 1. 部署 master 工作机（服务器）

master 是一个长驻容器，以 worker 镜像为基底加 docker CLI：

```bash
# /data/autodev/build/v4/Dockerfile.master（随 build.sh 夜间重建）
docker build --build-arg DOCKER_GID=$(getent group docker | cut -d: -f3) \
  -f /data/autodev/build/v4/Dockerfile.master -t autodev-master:current /data/autodev/build/v4
docker run -d --name autodev-master --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /data/autodev:/data/autodev \
  -v /home/autodev:/home/autodev \
  autodev-master:current
docker exec autodev-master sh -c 'id -u; docker --version; jira --version'   # 期望 1001 + 两个版本号
```

宿主路径与容器路径必须相同：worktree 的 `.git` 文件里写的是宿主绝对路径，差一个字符就 `not a git repository`。

在 OpenVort「工作节点」登记为 docker 类型，config：

```json
{"container_id": "autodev-master", "autodev_master": true, "max_slots": 1}
```

- `autodev_master: true` 开启员工侧命令黑名单（见 §5）。
- `max_slots` 是**节点级**并发上限，同机所有项目共享。内存判据：可用内存 ≥ slots × 4 G + 1 G。
  并发 > 1 之前必须先把 `worker.sh` 的 usage.jsonl 改回每轮独立文件，否则用量串账。

## 2. 插件配置

系统设置 → 插件 → AutoDev：`ai_member_id` = 全公司唯一的自动交付 AI 员工的成员 ID。它是队列的判据（story 指派给它）也是两条全局定时任务的 owner。把这位员工绑定到 master 节点即可在聊天里查状态。

## 3. 项目配置（项目详情页 → 自动交付）

| 字段 | 说明 |
|---|---|
| master 节点 | 上面登记的节点 |
| 仓路径 | 宿主上交付仓的绝对路径（主仓，不是 worktree）；kit 仓须在同父目录 |
| Jira 项目 key | 同步与派发都限定在这个项目 |
| 同步 JQL / 窗口 | 空则 `updated >= -<窗口>d`；首次用大窗口全量 |
| 状态映射 | Jira 状态名 → story 状态；默认见 `contract.DEFAULT_STATUS_MAP` |
| 镜像 / 模型 / 超时 | 透传给 `worker.sh` 的 `AUTODEV_*` |
| 日上限 / 熔断阈值 | 项目级闸门 |
| 真交付 | `deliver=false` 时 worker 以 `AUTODEV_DELIVER=0` 跑，验证通过即停（退出码 15）；上线先跑几张再翻 |
| 平台系统用户 | `HCM_BASE_URL / HCM_USERNAME / HCM_PASSWORD`，密码加密存储；派发前写进仓内 `03_config/.env` 的这三行，其余行（含 hcmo 自刷的 `HCM_TOKEN`）逐字保留，内容相同不写 |
| 非密变量 | 传给 worker 的额外 env；键名含 TOKEN/SECRET/PASSWORD 等一律拒绝 |
| 单价 | 每百万 token 的 input / output 单价；0 = 只报 token |

通用密钥（Jira token、GitLab PAT、CodeBuddy、ocx）仍是 `/home/autodev` 下的只读文件，OpenVort 不碰。

## 4. 队列、闸门与定时任务

- **队列** = 本项目 · `state = dev_assign` · `assignee = AI 员工` · 有 Jira 映射的 story。人把 story 指派给 AI 员工就是选单；系统从不自动指派。
- **同步**（全局任务 `autodev_sync`）：经 master 跑 `jira --json issue list`，单向投影为 story；Jira 是唯一真相，OpenVort 不写 Jira。story 状态只在 Jira 状态**变化**时被覆盖，人在 OpenVort 推进的 `dev_assign` 不会被打回。
- **派发**（全局任务 `autodev_dispatch`）：遍历启用项目按上次派发时间轮转；六道闸门依次：未启用 · 暂停 · 熔断（最近 N 次全 failed）· 节点 slot · 项目日上限 · 同单互斥。派出后 story → `in_progress`。
- **回收**：每 60 s 读 `<dispatch_dir>/rc`，收口后读 `summary.json` 与 `usage-report.py --ticket`；`delivered → testing`、`failed/lost → dev_assign`，并在 story 上加系统评论。OpenVort 重启不影响在跑的 worker。
- 两条全局任务由「自动交付」页启停（也出现在定时任务列表里）；它们是确定性代码，不经 LLM。

退出码含义：`GET /api/autodev/exit-codes`（与 `run-task.sh` 契约同源）。

## 5. 员工侧黑名单（漏拦面声明）

绑定 master 的员工在 `node_shell` / `node_file_read` / `node_file_write` 上会被拒绝：`worker.sh`、`docker` 子命令、`/home/autodev/.*`、`.git-credentials` / `.jira-cli` / `glab-cli` / `CodeBuddyExtension` / `.opencodex/config.json`、`03_config/.env`、`docker.sock`。判据在 `core/execution/node_guard.py`，命中记日志。

**拦不住什么**：改名后的脚本副本、经 `python -c` / `base64` 拼出的命令、通过其它已放行工具间接读文件。黑名单是可扩展起点不是完备集——发现新绕法往 `node_guard` 加模式，不要只在对话里绕过。

## 6. REST

`/api/autodev`：`/nodes` · `/global`（GET）· `/global/{autodev_dispatch|autodev_sync}`（PUT，admin）· `/projects/{id}`（GET / PUT admin）· `/projects/{id}/queue` · `/projects/{id}/sync`（POST admin）· `/projects/{id}/dispatch`（POST admin，可带 `issue_key`）· `/projects/{id}/pause|resume`（admin）· `/projects/{id}/runs` · `/projects/{id}/stats` · `/poll`（admin）· `/exit-codes`。
