"""autodev 契约层：纯函数判据。每条都有正例与反例，缺反例的断言不算判据。"""

import json
import shlex

import pytest

from openvort.plugins.autodev import contract as ct


def test_outcome_mapping_covers_all_documented_codes():
    assert ct.outcome_for(0) == ct.OUTCOME_DELIVERED
    assert ct.outcome_for(15) == ct.OUTCOME_VERIFIED
    assert ct.outcome_for(19) == ct.OUTCOME_NO_CHANGE
    assert ct.outcome_for(None) == ""
    for rc in ct.EXIT_CODES:
        if rc not in (0, 15, 19):
            assert ct.outcome_for(rc) == ct.OUTCOME_FAILED, rc
    assert ct.describe_exit(999).startswith("未知退出码")
    assert ct.describe_exit(None) == "未结束"


@pytest.mark.parametrize("bad", [
    {"GITLAB_TOKEN": "x"}, {"api_key": "x"}, {"Jira-Pass": "x"}, {"AUTODEV_MODEL": "x"}, {"1ABC": "x"},
])
def test_validate_env_rejects_secrets_reserved_and_malformed(bad):
    with pytest.raises(ValueError):
        ct.validate_env(bad)


def test_validate_env_accepts_plain_vars_and_stringifies():
    out = ct.validate_env({"HTTP_PROXY": "http://p:1", "MAX_RETRY": 3})
    assert out == {"HTTP_PROXY": "http://p:1", "MAX_RETRY": "3"}


# ---------- Jira 同步 ----------


def test_jira_sync_cmd_default_and_quoting():
    default = ct.jira_sync_cmd("TPYBX", "", 200)
    assert default.startswith("jira --json issue list -p TPYBX --jql ") and default.endswith("--max 200")
    parts = shlex.split(default)
    jql = parts[parts.index("--jql") + 1]
    # 默认范围 = 机器人自己的足迹：在办的 + 历史上由它流转到「已修复」的。不写死账号名。
    assert jql == ct.DEFAULT_SYNC_JQL
    assert "currentUser()" in jql and ct.STATUS_FIXED in jql and "assignee" in jql
    custom = ct.jira_sync_cmd("TPYBX", "labels = auto AND status = OPEN", 50)
    parts = shlex.split(custom)
    assert parts[parts.index("--jql") + 1] == "labels = auto AND status = OPEN"
    with pytest.raises(ValueError):
        ct.jira_sync_cmd("", "", 50)


JIRA_SAMPLE = json.dumps([
    {"key": "TPYBX-24", "self": "https://jira.x.cn/rest/api/2/issue/1", "fields": {
        "summary": "权限体系改造", "description": "正文", "status": {"name": "OPEN"}, "priority": {"name": "High"},
        "assignee": {"displayName": "顾问甲", "name": "ga"}, "issuetype": {"name": "需求"}}},
    {"key": "TPYBX-35",
     "fields": {"summary": "UI 优化", "status": {"name": "新增"}, "priority": None, "assignee": None}},
])


def test_parse_jira_issues_flattens_list_shape():
    items = ct.parse_jira_issues(JIRA_SAMPLE)
    assert [i["key"] for i in items] == ["TPYBX-24", "TPYBX-35"]
    assert items[0] == {"key": "TPYBX-24", "url": "https://jira.x.cn/browse/TPYBX-24", "summary": "权限体系改造",
                        "description": "正文", "status": "OPEN", "priority": "High",
                        "assignee": "顾问甲", "type": "需求"}
    assert items[1]["priority"] == "" and items[1]["assignee"] == "" and items[1]["description"] == ""
    assert items[1]["url"] == ""  # 没有 self 就没有地址，不猜
    assert len(ct.parse_jira_issues(json.dumps({"issues": json.loads(JIRA_SAMPLE)}))) == 2
    assert ct.parse_jira_issues("[]") == []


def test_parse_jira_issues_asserts_on_keyless_rows():
    with pytest.raises(AssertionError):
        ct.parse_jira_issues(json.dumps([{"fields": {"summary": "no key"}}]))


def test_status_map_fixed_table():
    table = ct.STATUS_MAP
    assert table["OPEN"] == ct.STATE_IN_PROGRESS and table["已修复"] == ct.STATE_TESTING
    # 覆盖 jira.hcmcloud.cn 实际工作流的全部 9 个状态名（2026-09-08 从 TPYBX + HC 实测）
    assert set(table) == {"新增", "补充说明", "待确认", "转支持确认中", "OPEN",
                          "已修复", "测试中", "不处理", "CLOSE"}
    assert table["CLOSE"] == ct.STATE_DONE and table["测试中"] == ct.STATE_TESTING
    assert ct.map_state("表外", table) is None
    assert ct.map_priority("High") == 2 and ct.map_priority("") == 3


def test_sync_decision_overrides_only_on_jira_change():
    table = ct.STATUS_MAP
    # 首次导入：按映射置初态；表外状态 → submitted 且标记 unmapped
    assert ct.sync_decision(existing=False, prev_status=None, jira_status="OPEN", table=table) == \
        ct.SyncDecision(create=True, set_state=ct.STATE_IN_PROGRESS, unmapped_status=False)
    assert ct.sync_decision(existing=False, prev_status=None, jira_status="怪状态", table=table) == \
        ct.SyncDecision(create=True, set_state=ct.STATE_SUBMITTED, unmapped_status=True)
    # Jira 未变：不动（人推进的 dev_assign 保住）
    assert ct.sync_decision(existing=True, prev_status="新增", jira_status="新增", table=table).set_state is None
    # Jira 打回 OPEN：覆盖
    assert ct.sync_decision(existing=True, prev_status="已修复", jira_status="OPEN", table=table).set_state \
        == ct.STATE_IN_PROGRESS
    # Jira 变到表外状态：不动 + 告警
    d = ct.sync_decision(existing=True, prev_status="OPEN", jira_status="怪状态", table=table)
    assert d.set_state is None and d.unmapped_status


# ---------- 派发 ----------


def _spec(**over):
    base = dict(worker_script="/data/autodev/build/v4/worker.sh", repo_path="/data/autodev/repos/cpic",
                issue_key="TPYBX-754", dispatch_dir="/data/autodev/state/dispatch/TPYBX-754-x",
                image="autodev-worker:current", model="custom-local:deepseek-v4-pro", deliver=False,
                timeout_seconds=21600, env={"HTTP_PROXY": "http://p:1 q"})
    base.update(over)
    return ct.LaunchSpec(**base)


def test_launch_cmd_shape():
    cmd = ct.launch_cmd(_spec())
    assert "nohup setsid bash -c " in cmd and cmd.endswith("echo launched")
    assert "already-finished" in cmd  # 同一派发目录不许二次点火
    inner = shlex.split(cmd.split("bash -c ", 1)[1].rsplit(" > /dev/null", 1)[0])[0]
    assert "AUTODEV_DELIVER=0" in inner and "AUTODEV_TIMEOUT=21600" in inner
    assert "HTTP_PROXY='http://p:1 q'" in inner
    assert inner.endswith("> /data/autodev/state/dispatch/TPYBX-754-x/worker.log 2>&1; "
                          "echo $? > /data/autodev/state/dispatch/TPYBX-754-x/rc")
    assert "/data/autodev/build/v4/worker.sh TPYBX-754 --repo /data/autodev/repos/cpic" in inner
    assert "AUTODEV_DELIVER=1" in ct.launch_cmd(_spec(deliver=True))


@pytest.mark.parametrize("over", [{"issue_key": "x; rm -rf /"}, {"issue_key": "tpybx-1"}, {"repo_path": "repos/cpic"}])
def test_launch_cmd_rejects_unsafe_inputs(over):
    with pytest.raises(ValueError):
        ct.launch_cmd(_spec(**over))


def test_parse_probe_running_and_finished():
    assert ct.parse_probe("RC=\n") == ct.Probe(None, "", "", "")
    text = ("RC=0\n[worker] 结果 rc=0：/req 跑完\n"
            "[worker] 摘要 /data/autodev/state/runs/TPYBX-754-20260907-173206/summary.json\n"
            "[worker] 运行目录 /data/autodev/state/runs/TPYBX-754-20260907-173206\n")
    p = ct.parse_probe(text)
    assert p.rc == 0 and p.summary_path.endswith("summary.json")
    assert p.run_dir.endswith("TPYBX-754-20260907-173206") and p.verdict_line.startswith("结果 rc=0")
    assert ct.parse_probe("RC=abc\n").rc is None


def test_parse_summary_requires_ticket():
    assert ct.parse_summary('{"ticket":"A-1","exit_code":0}')["ticket"] == "A-1"
    with pytest.raises(AssertionError):
        ct.parse_summary('{"exit_code":0}')


def test_pick_usage_matches_run_dir_name():
    report = json.dumps([
        {"run": "TPYBX-571-20260903-115307", "ticket": "TPYBX-571", "inputTokens": 10, "outputTokens": 2},
        {"run": "TPYBX-571-20260903-122752", "ticket": "TPYBX-571", "inputTokens": 30, "outputTokens": 4},
    ])
    assert ct.pick_usage(report, "/data/autodev/state/runs/TPYBX-571-20260903-122752/")["inputTokens"] == 30
    assert ct.pick_usage(report, "/x/TPYBX-571-20260903-000000") is None


def test_compute_cost_fixed_price_table(monkeypatch):
    monkeypatch.setitem(ct.MODEL_PRICES, "m-test", (1.0, 4.0))
    assert ct.compute_cost(2_000_000, 500_000, "m-test") == 4.0
    assert ct.compute_cost(2_000_000, 500_000, "unknown-model") == 0
    assert ct.MODEL in ct.MODEL_PRICES  # 当前固定模型必须有价，否则统计只报 token
    fixed = ct.fixed_params()
    assert fixed["model"] == ct.MODEL and fixed["price_out_per_m"] == ct.MODEL_PRICES[ct.MODEL][1]
    assert fixed["default_sync_jql"] == ct.DEFAULT_SYNC_JQL


# ---------- .env 三行合并 ----------

VALUES = {"HCM_BASE_URL": "https://h", "HCM_USERNAME": "sysuser", "HCM_PASSWORD": "p@ss=1"}


def test_env_merge_keeps_token_line_verbatim_and_other_lines():
    existing = "# comment\nHCM_BASE_URL=https://old\nHCM_USERNAME=old\nHCM_PASSWORD=old\nHCM_TOKEN=abc.def==\nEXTRA=1\n"
    merged = ct.env_merge(existing, VALUES)
    assert merged == ("# comment\nHCM_BASE_URL=https://h\nHCM_USERNAME=sysuser\nHCM_PASSWORD=p@ss=1\n"
                      "HCM_TOKEN=abc.def==\nEXTRA=1\n")
    assert ct.env_changed_keys(existing, VALUES) == ["HCM_BASE_URL", "HCM_USERNAME", "HCM_PASSWORD"]


def test_env_merge_identical_returns_none_and_missing_file_creates():
    same = "HCM_BASE_URL=https://h\nHCM_USERNAME=sysuser\nHCM_PASSWORD=p@ss=1\nHCM_TOKEN=t\n"
    assert ct.env_merge(same, VALUES) is None
    assert ct.env_merge(same.rstrip("\n"), VALUES) is None  # 末尾无换行也算相同
    assert ct.env_merge("", VALUES) == "HCM_BASE_URL=https://h\nHCM_USERNAME=sysuser\nHCM_PASSWORD=p@ss=1\n"
    # 只缺 token 行以外的某一行：补在末尾，其余不动
    assert ct.env_merge("HCM_TOKEN=t\nHCM_USERNAME=sysuser\n", VALUES) == \
        "HCM_TOKEN=t\nHCM_USERNAME=sysuser\nHCM_BASE_URL=https://h\nHCM_PASSWORD=p@ss=1\n"


def test_env_merge_rejects_missing_values():
    with pytest.raises(ValueError, match="凭据缺项：HCM_PASSWORD"):
        ct.env_merge("", {**VALUES, "HCM_PASSWORD": ""})


def test_env_write_cmd_uses_stdin_and_0600():
    cmd = ct.env_write_cmd("/data/autodev/repos/cpic/03_config/.env")
    assert cmd.startswith("umask 077") and "cat > /data/autodev/repos/cpic/03_config/.env" in cmd
    assert cmd.endswith("chmod 600 /data/autodev/repos/cpic/03_config/.env")


# ---------- 闸门 ----------


def _gate(**over):
    base = dict(enabled=True, paused=False, node_max_slots=1, node_running=0, daily_cap=3, started_today=0,
                failure_threshold=3, recent_outcomes=())
    base.update(over)
    return ct.gate(ct.GateInput(**base))


def test_gate_branches():
    assert _gate() == ct.GateResult(1, "")
    assert _gate(node_max_slots=3, daily_cap=2).allowed == 2
    assert _gate(enabled=False).reason == "项目未启用派发"
    assert _gate(paused=True).reason == "派发已暂停"
    assert _gate(node_running=1).reason.startswith("slot 已满")
    assert _gate(started_today=3).reason.startswith("今日已达日上限")
    assert _gate(recent_outcomes=("failed", "failed", "failed")).reason.startswith("熔断")
    assert _gate(recent_outcomes=("failed", "delivered", "failed")).allowed == 1
    assert _gate(failure_threshold=0, recent_outcomes=("failed",) * 5).allowed == 1
    # 熔断先于 slot：熔断中即使 slot 空也不派
    assert _gate(node_max_slots=5, recent_outcomes=("failed",) * 3).reason.startswith("熔断")


def test_node_max_slots_parsing():
    assert ct.node_max_slots({}) == 1
    assert ct.node_max_slots({"max_slots": "3"}) == 3
    assert ct.node_max_slots({"max_slots": 0}) == 1
    assert ct.node_max_slots({"max_slots": "x"}) == 1


def test_story_title_and_description_carry_jira_key():
    self_link = "https://jira.hcmcloud.cn/rest/api/2/issue/357017"
    url = ct.browse_url(self_link, "TPYBX-730")
    assert url == "https://jira.hcmcloud.cn/browse/TPYBX-730"
    assert ct.browse_url("", "TPYBX-730") == "" and ct.browse_url(self_link, "") == ""
    # 每轮重建，重复同步不会把单号叠加成 "K K 标题"
    t = ct.story_title("TPYBX-730", "培训设置-供应商信息")
    assert t == "TPYBX-730 培训设置-供应商信息"
    assert ct.story_title("TPYBX-730", "") == "TPYBX-730"
    d = ct.story_description(url, "正文")
    assert d.startswith("Jira: " + url) and d.endswith("正文")
    assert ct.story_description("", "正文") == "正文"
