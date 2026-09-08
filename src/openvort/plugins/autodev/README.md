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

插件管理 → 已安装 → AutoDev → 设置：从下拉里选那位自动交付 AI 员工（候选 = 全部数字员工，未绑工作机的会标注；列表由服务每 60 s 刷新一次快照）。它有三个作用：队列判据（story 指派给它）、两条全局定时任务的 owner、**master 的来源**——派发与同步用的节点就是这位员工绑定的工作机（成员的 `remote_node_id`），项目里不再单独选 master。员工没绑机时派发与同步直接报「AI 员工未绑定工作机」。

## 3. 项目配置（项目详情页 → 自动交付）

每项目只配这些（其余都是固定参数，见 §3.1）：

| 字段 | 说明 |
|---|---|
| 仓路径 | 宿主上交付仓的绝对路径（主仓，不是 worktree）；kit 仓须在同父目录 |
| Jira 项目 key | 同步与派发都限定在这个项目 |
| 同步 JQL | 留空即用默认（见 §3.1），只同步这条流水线自己的单；填了就整条替换 |
| 真交付 | `deliver=false` 时 worker 以 `AUTODEV_DELIVER=0` 跑，验证通过即停（退出码 15）；上线先跑几张再翻 |
| 启用派发 | 关掉即不进全局派发轮转 |
| 平台系统用户 | `HCM_BASE_URL / HCM_USERNAME / HCM_PASSWORD`，密码加密存储；派发前写进仓内 `03_config/.env` 的这三行，其余行（含 hcmo 自刷的 `HCM_TOKEN`）逐字保留，内容相同不写 |
| 非密变量 | 传给 worker 的额外 env；键名含 TOKEN/SECRET/PASSWORD 等一律拒绝 |

通用密钥（Jira token、GitLab PAT、CodeBuddy、ocx）仍是 `/home/autodev` 下的只读文件，OpenVort 不碰。

### 3.1 固定参数（不是项目属性）

全流水线一套值，写死在 `contract.py`，页面只读展示，`GET /api/autodev/global` 的 `fixed` 字段也返回：

| 常量 | 值 | 改动条件 |
|---|---|---|
| `WORKER_SCRIPT` / `DISPATCH_ROOT` / `USAGE_REPORT` | `/data/autodev/...` 三条路径 | 服务器 `build/v4` 布局变了 |
| `WORKER_IMAGE` | `autodev-worker:current` | 换镜像 tag 策略 |
| `MODEL` | `custom-local:deepseek-v4-pro` | 换模型 |
| `TIMEOUT_SECONDS` | 21600（6 h） | worker 墙钟上限调整 |
| `DAILY_CAP` / `FAILURE_THRESHOLD` | 3 / 3 | 闸门策略调整 |
| `MODEL_PRICES` | deepseek-v4-pro = ¥9 / ¥27 每百万 token（高峰价） | 价目变动，源见 vault `codebuddy-本机模型价格` |
| `DEFAULT_SYNC_JQL` | `(assignee = currentUser() OR status changed to 已修复 by currentUser()) ORDER BY updated DESC`——在办的加历史交付过的，账号取 master 上 jira CLI 的登录身份 | 取单口径变了 |
| `STATUS_MAP` | 新增·补充说明·待确认·转支持确认中→submitted、OPEN→in_progress、已修复·测试中→testing、不处理→rejected、CLOSE→done | Jira 工作流出现新状态名 |

费用按运行记录里的模型查价；模型不在价目表则费用为 0，页面显示「未配单价」。并发上限 `max_slots` 仍在 master 节点 config 里（同机共享，不是项目属性）。

## 4. 队列、闸门与定时任务

- **队列** = 本项目 · `state = dev_assign` · `assignee = AI 员工` · 有 Jira 映射的 story。人把 story 指派给 AI 员工就是选单；系统从不自动指派。
- **同步**（全局任务 `autodev_sync`）：经 master 跑 `jira --json issue list`，单向投影为 story；Jira 是唯一真相，OpenVort 不写 Jira。story 状态只在 Jira 状态**变化**时被覆盖，人在 OpenVort 推进的 `dev_assign` 不会被打回。
- **派发**（全局任务 `autodev_dispatch`）：遍历启用项目按上次派发时间轮转；六道闸门依次：未启用 · 暂停 · 熔断（最近 3 次全 failed）· 节点 slot · 项目日上限（3）· 同单互斥。派出后 story → `in_progress`。
- **回收**：每 60 s 读 `<dispatch_dir>/rc`，收口后读 `summary.json` 与 `usage-report.py --ticket`；`delivered → testing`、`failed/lost → dev_assign`，并在 story 上加系统评论。OpenVort 重启不影响在跑的 worker。
- 两条全局任务由「自动交付」页启停（也出现在定时任务列表里）；它们是确定性代码，不经 LLM。

退出码含义：`GET /api/autodev/exit-codes`（与 `run-task.sh` 契约同源）。

## 5. 员工侧黑名单（漏拦面声明）

绑定 master 的员工在 `node_shell` / `node_file_read` / `node_file_write` 上会被拒绝：`worker.sh`、`docker` 子命令、`/home/autodev/.*`、`.git-credentials` / `.jira-cli` / `glab-cli` / `CodeBuddyExtension` / `.opencodex/config.json`、`03_config/.env`、`docker.sock`。判据在 `core/execution/node_guard.py`，命中记日志。

**拦不住什么**：改名后的脚本副本、经 `python -c` / `base64` 拼出的命令、通过其它已放行工具间接读文件。黑名单是可扩展起点不是完备集——发现新绕法往 `node_guard` 加模式，不要只在对话里绕过。

## 6. REST

`/api/autodev`：`/global`（GET，含 `ai_member_id` / `master` / `fixed` / 两条任务状态）· `/global/{autodev_dispatch|autodev_sync}`（PUT，admin）· `/projects/{id}`（GET / PUT admin）· `/projects/{id}/queue` · `/projects/{id}/sync`（POST admin）· `/projects/{id}/dispatch`（POST admin，可带 `issue_key`）· `/projects/{id}/pause|resume`（admin）· `/projects/{id}/runs` · `/projects/{id}/stats` · `/poll`（admin）· `/exit-codes`。
