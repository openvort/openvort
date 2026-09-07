# Tasks · openvort-autodev-master

> 落点：本仓 `feat/autodev-master`（盘上草稿按 design 决策 13 改）· 服务器 `/data/autodev` · vault。
> 「验证」= 可重跑的命令或可观测产物；写 `已跑过` 不算。

## 0. 前置（不依赖 OpenVort 新代码）

- [x] 0.1 合并 `DockerExecutor.send_instruction` 签名修复 · 验证：`pytest tests/test_remote_executor_signature.py` 绿，且 `git stash` 后同文件红
- [x] 0.2 服务器 `worker.sh`：usage.jsonl 改回每轮独立文件（`cp -a` 形态，去掉单文件挂载与占位逻辑）· 验证：跑一单后 `<run>/home/.opencodex/usage.jsonl` 存在且 `usage-report.py --ticket <单号> --json` 归属到该 run
- [x] 0.3 服务器 `build/v4/Dockerfile.master`（FROM `autodev-worker:current` + docker CLI + docker 组，`USER autodev`），`build.sh` 夜间同步重建 · 验证：`docker run --rm autodev-master:current sh -c 'id -u; docker --version; jira --version'` 输出 1001 与两个版本号
- [x] 0.4 起 `autodev-master` 容器（挂 docker.sock、`/data/autodev`、`/home/autodev` 同路径）并在 OpenVort 登记为 docker 节点，config 含 `container_id`、`autodev_master: true`、`max_slots: 1` · 验证：节点页「测试连接」为 running；`docker exec autodev-master ls /data/autodev/repos/cpic/.git` 非空
- [x] 0.5 vault：`hcm-west-delivery.md` 加定调修订段；`openvort.md` 加本 change 指针；`autodev-pipeline/README.md` 服务器实况更新 · 验证：三文件 `grep -c openvort-autodev-master` 各 ≥ 1

## 1. 核心机制（openvort core）

- [x] 1.1 `schedule_service`：`ACTION_HANDLERS` 注册表 + `register_action_handler`；`_execute_job` 先查表，查到跳过 prompt 校验与 Agent，收尾与通知复用 · 验证：`pytest tests/test_schedule_action_handlers.py`（含无 prompt 成功、处理器抛错标 failed、agent_chat 仍要求 prompt）
- [x] 1.2 `node_tools`：节点 config `autodev_master: true` 时对 `node_shell` / `node_file_write` / `node_file_read` 施加黑名单，命中拒绝并记日志；非 master 节点不受影响 · 验证：新增 `tests/test_node_tools_master_guard.py` 覆盖 spec 三个场景（worker.sh 拒绝、非 master 放行、usage-report 放行）
- [x] 1.3 `db/engine.py` 导入 autodev models；`pyproject.toml` 加 entry point · 验证：`python -c "from importlib.metadata import entry_points; print([e.name for e in entry_points(group='openvort.plugins')])"` 含 autodev

## 2. 插件数据模型与配置

- [x] 2.1 `AutodevProject`：去掉 `max_slots`（挪到节点 config）与 JQL 直查字段；新增 `sync_jql`、`sync_window_days`、`status_map_json`、`last_dispatched_at`、平台三项（`hcm_base_url`、`hcm_username`、`hcm_password_enc`）· 验证：sqlite `create_all` 建表通过，`tests/test_autodev_service.py` 里的 upsert 用例覆盖新字段
- [ ] 2.2 插件全局配置（`get_config_schema`）：`ai_member_id`（全局 AI 员工）· 验证：系统设置页可选员工并保存；服务读到的 id 与 DB 一致
- [x] 2.3 `AutodevRun` 增加 `story_id` · 验证：回收后 `story_id` 非空（4.3）

## 3. Jira → story 投影

- [x] 3.1 `contract`：`jira_sync_cmd`（`project = KEY` + JQL + `--max`）、`parse_jira_issues`（列表形态、key 断言）、默认状态映射表与 `map_state` · 验证：`tests/test_autodev_contract.py` 覆盖首次窗口、零命中、表外状态告警
- [x] 3.2 `service.sync_project`：创建/更新 story、写 `FlowExternalMapping(adapter=jira, sync_cursor=上次状态)`、仅状态变化时覆盖 · 验证：`tests/test_autodev_sync.py` 覆盖 spec 四个场景（重复同步计数不变、人推进 dev_assign 不被打回、打回 OPEN → in_progress、零命中不删）
- [x] 3.3 `autodev_sync` 全局 action 处理器遍历启用项目 · 验证：处理器测试断言遍历顺序与每项目独立失败不互相影响

## 4. 派发与台账

- [x] 4.1 `contract.gate` 六道闸门（slot 按节点、日上限与熔断按项目、暂停、启用、同单互斥）+ `launch_cmd` / `probe_cmd` / `parse_probe` / `pick_usage` / `compute_cost` · 验证：`tests/test_autodev_contract.py` 每道门有正反例
- [x] 4.2 `service.dispatch_all`：轮转、队列取自 story、派出后 story → `in_progress`、先落记录再起容器、启动失败收口 · 验证：`tests/test_autodev_service.py` 覆盖 spec「slot 由节点共享」「轮转公平」「同单互斥」「deliver 关闭」
- [x] 4.3 `service.poll_once`：读 rc / 摘要 / 用量收口，story 表内动作 + 系统评论，lost 判定 · 验证：测试覆盖「重启后回收」「摘要缺失」「用量缺失」「失败回 dev_assign」
- [x] 4.4 `autodev_dispatch` 全局 action 处理器 + 插件激活时按需创建两条禁用态全局任务 · 验证：激活后 `schedule_jobs` 出现两条 `enabled=false` 记录，且重复激活不重复创建

## 5. 每项目凭据

- [x] 5.1 密码 Fernet 存储、读出脱敏、`****` 前缀视为未改 · 验证：router 测试断言返回值末 4 位与不覆盖
- [x] 5.2 `contract.env_merge`：只替换三行、保留其余行、内容相同返回 None · 验证：contract 测试覆盖 token 行逐字保留与相同不写
- [x] 5.3 派发前经 master stdin 写 `03_config/.env`（0600），缺项拒绝派发 · 验证：service 测试断言写命令用 stdin 且缺密码时理由为「凭据缺项：HCM_PASSWORD」

## 6. AI 员工工具与提示

- [x] 6.1 `autodev_status` / `autodev_runs` 只读工具（返回去掉内部路径）+ `prompts/autodev.md` · 验证：工具单测断言返回键集合不含 `dispatch_dir/run_dir/worktree`
- [ ] 6.2 员工绑定 master 后端到端：问「队列几张 / 今天完成几张 / 某单花了多少」能答且数字与 REST 一致 · 验证：Web 聊天截图 + `/api/autodev/projects/<id>/stats` 对照

## 7. REST 与前端

- [x] 7.1 `/api/autodev`：项目配置读写（admin）、队列、运行记录、统计、立即派发、暂停/恢复、全局任务启停、节点列表 · 验证：`tests/test_autodev_router.py` 用 TestClient 覆盖 403 与主要读写
- [x] 7.2 `web/src/api/autodev.ts` + 项目详情页「自动交付」tab（配置表单 / 队列 / 运行记录 / 统计 / 操作按钮）· 验证：`pnpm build` 通过；浏览器截图四个区块有数据
- [x] 7.3 README 使用说明（master 节点搭建、项目配置项、闸门与退出码表、黑名单漏拦面）· 验证：文档里每条命令在服务器实跑一次

## 8. 上线（cpic）

- [ ] 8.1 `update.sh feat/autodev-master` 部署；cpic 填配置，`deliver=false`；启用同步任务 · 验证：story 数量 = `jira --json issue list -p TPYBX --jql <同 JQL> | jq length`
- [ ] 8.2 指派 1 张 story → 立即派发 → 回收 exit 15 与用量 · 验证：运行记录 outcome=verified，token > 0，story=dev_assign 未变（verified 不动状态）
- [ ] 8.3 启用全局派发任务跑 3 张（仍 `deliver=false`）· 验证：三条记录 trigger=schedule；无同单重复；slot 从未超 1
- [ ] 8.4 翻 `deliver=true` 跑 1 张真交付 · 验证：记录 outcome=delivered，MR 链接可打开，Jira 单状态「已修复」且经办人为建单人，story=testing
- [ ] 8.5 复盘写入 `autodev-pipeline/README.md` 与 kit `docs/rules-casebook.md`（只写换一张单还会再犯的）· 验证：两文件各新增一段并含日期
