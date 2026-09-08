"""AutoDev 契约层——纯函数，不碰 DB、不碰 docker。

这里是 master 与 worker.sh 之间的全部接口：退出码表、命令拼装、产物解析、闸门判定、
Jira → story 的状态映射、.env 三行合并。判据全部机械化，LLM 不参与派发决策。
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from datetime import date, datetime

# 退出码契约：与 /data/autodev/build/v4/run-task.sh + worker.sh 同源，改那边必须同步改这里
EXIT_CODES: dict[int, str] = {
    0: "/req 跑完，收口四步全绿——分支已推 · MR 已开 · 工单已评论 · 复盘已写，未合并",
    10: "CodeBuddy 没产出任何事件",
    11: "/req 没产出 33_runs/<单号>/——它没跑到阶段 1 之后",
    12: "收口停在某步（finish.py 打印停在哪一步）",
    15: "按 AUTODEV_DELIVER=0 停在交付前——已提交到本地分支，未收口",
    17: "没有新提交，且有工具调用因「非交互模式无法批准」被拒——结论不可信",
    18: "工作区有未提交变更——/req 中途停了，没把半成品推出去",
    19: "没有新提交，也没有被拒的工具调用——模型判断无需改动，或它停在了别处",
    20: "镜像坏了：codebuddy 或 ocx 不在 PATH",
    21: "配置挂载缺失或不可写",
    22: "认证不通过——配置过期或模型端点够不着",
    24: "运行工作区不是 git 仓（多半是主仓没挂在同名路径上）",
    25: "AUTODEV_MODEL 不受支持",
    26: "超时被杀",
    27: "容器内 ocx 起不来",
    28: "CLI 装在镜像里但跑不起来",
    30: "宿主侧预检不通过",
    31: "主仓或 kit 仓拉不到最新（工作区不干净 / fetch 失败 / ff-only 拉不动）",
    32: "多棵 worktree 都有本单的 33_runs/<单号>/——没替你选该推哪一棵",
    33: "停滞：codebuddy 长时间没产出任何事件，被看门狗杀掉",
    125: "docker 自身启动失败",
    126: "docker 自身启动失败",
    127: "docker 自身启动失败",
}

OUTCOME_DELIVERED = "delivered"
OUTCOME_VERIFIED = "verified"
OUTCOME_NO_CHANGE = "no_change"
OUTCOME_FAILED = "failed"

# story 状态（vortflow StoryState 的子集，本插件只写这几个）
STATE_SUBMITTED = "submitted"
STATE_DEV_ASSIGN = "dev_assign"
STATE_IN_PROGRESS = "in_progress"
STATE_TESTING = "testing"
STATE_REJECTED = "rejected"
STATE_DONE = "done"

# Jira 状态名 → story state（固定表，不按项目覆盖）
# 取自 jira.hcmcloud.cn 的实际工作流：TPYBX 与 HC 两个项目共 9 个状态名，这里全覆盖。
# 表外状态一律保留 story 现状并记一次告警——发现新状态名往这里加，别改成猜。
STATUS_MAP: dict[str, str] = {
    "新增": STATE_SUBMITTED,
    "补充说明": STATE_SUBMITTED,
    "待确认": STATE_SUBMITTED,
    "转支持确认中": STATE_SUBMITTED,
    "OPEN": STATE_IN_PROGRESS,
    "已修复": STATE_TESTING,
    "测试中": STATE_TESTING,
    "不处理": STATE_REJECTED,
    "CLOSE": STATE_DONE,
}

# Jira 优先级名 → story priority（1=紧急 2=高 3=中 4=低）
PRIORITY_MAP: dict[str, int] = {"Highest": 1, "High": 2, "Medium": 3, "Low": 4, "Lowest": 4}

# ---------- 固定参数：部署级常量，不按项目配置；改这里要同步改服务器 build/v4 ----------
WORKER_SCRIPT = "/data/autodev/build/v4/worker.sh"
WORKER_IMAGE = "autodev-worker:current"
MODEL = "custom-local:deepseek-v4-pro"
DISPATCH_ROOT = "/data/autodev/state/dispatch"
USAGE_REPORT = "/data/autodev/bin/usage-report.py"
TIMEOUT_SECONDS = 21600  # worker 内 codebuddy 墙钟上限（6 h）
DAILY_CAP = 3  # 每项目每日最多起几次 worker
FAILURE_THRESHOLD = 3  # 每项目最近 N 次已结束运行全 failed 即熔断
# 元 / 百万 token：(input, output)。价目源 vault codebuddy-本机模型价格-20260904（高峰价，不按峰谷切换）
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "custom-local:deepseek-v4-pro": (9.0, 27.0),
}


def fixed_params() -> dict:
    """给 API / 页面展示用的固定参数快照。"""
    price = MODEL_PRICES.get(MODEL)
    return {
        "worker_script": WORKER_SCRIPT, "worker_image": WORKER_IMAGE, "model": MODEL,
        "dispatch_root": DISPATCH_ROOT, "usage_report": USAGE_REPORT, "timeout_seconds": TIMEOUT_SECONDS,
        "daily_cap": DAILY_CAP, "failure_threshold": FAILURE_THRESHOLD,
        "price_in_per_m": price[0] if price else None, "price_out_per_m": price[1] if price else None,
        "status_map": dict(STATUS_MAP),
    }

# worker 结束后 story 的表内动作（spec: jira-projection）
OUTCOME_TO_STATE: dict[str, str | None] = {
    OUTCOME_DELIVERED: STATE_TESTING,
    OUTCOME_FAILED: STATE_DEV_ASSIGN,
    OUTCOME_VERIFIED: None,
    OUTCOME_NO_CHANGE: None,
}

_ENV_KEY_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_SECRET_HINT = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "APIKEY", "API_KEY", "CREDENTIAL")
_ISSUE_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")

HCM_ENV_KEYS = ("HCM_BASE_URL", "HCM_USERNAME", "HCM_PASSWORD")


def describe_exit(rc: int | None) -> str:
    if rc is None:
        return "未结束"
    return EXIT_CODES.get(rc, f"未知退出码 {rc}")


def outcome_for(rc: int | None) -> str:
    if rc is None:
        return ""
    if rc == 0:
        return OUTCOME_DELIVERED
    if rc == 15:
        return OUTCOME_VERIFIED
    if rc == 19:
        return OUTCOME_NO_CHANGE
    return OUTCOME_FAILED


def is_issue_key(s: str) -> bool:
    return bool(_ISSUE_KEY_RE.match(s or ""))


# ---------- 环境变量 ----------


def validate_env(env: dict) -> dict[str, str]:
    """非密环境变量白名单校验：键名必须是大写标识符，键名带密钥字样直接拒绝。

    密钥进 env 会在 docker inspect 与 /proc/1/environ 里明文可见（ADR-0002）。
    """
    out: dict[str, str] = {}
    for k, v in (env or {}).items():
        if not isinstance(k, str) or not _ENV_KEY_RE.match(k):
            raise ValueError(f"环境变量名不合法: {k!r}（只允许 [A-Z_][A-Z0-9_]*）")
        if any(h in k.upper() for h in _SECRET_HINT):
            raise ValueError(f"环境变量 {k} 看起来是密钥——密钥只能以只读文件挂在 master 节点上，不走 env")
        if k.startswith("AUTODEV_"):
            raise ValueError(f"环境变量 {k} 与 worker.sh 的保留前缀 AUTODEV_ 冲突，请用配置字段")
        out[k] = str(v)
    return out


# ---------- Jira 同步 ----------


def default_sync_jql(window_days: int) -> str:
    return f"updated >= -{int(window_days)}d ORDER BY updated DESC"


def jira_sync_cmd(jira_project_key: str, jql: str, window_days: int, max_results: int) -> str:
    """`jira --json issue list -p KEY --jql '<jql>' --max N`——jql 空则按窗口天数取增量。"""
    if not jira_project_key:
        raise ValueError("jira_project_key 未配置")
    effective = (jql or "").strip() or default_sync_jql(window_days)
    return (
        f"jira --json issue list -p {shlex.quote(jira_project_key)} "
        f"--jql {shlex.quote(effective)} --max {int(max_results)}"
    )


def parse_jira_issues(text: str) -> list[dict]:
    """把 `jira --json issue list` 的输出压成扁平结构。返回体是 issue 列表（无外层容器）。"""
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("issues", [])
    items: list[dict] = []
    for it in data:
        f = it.get("fields") or {}
        assignee = f.get("assignee") or {}
        if isinstance(assignee, dict):
            assignee_name = assignee.get("displayName") or assignee.get("name") or ""
        else:
            assignee_name = str(assignee)
        items.append({
            "key": it.get("key", ""),
            "summary": f.get("summary", "") or "",
            "description": f.get("description", "") or "",
            "status": (f.get("status") or {}).get("name", ""),
            "priority": (f.get("priority") or {}).get("name", ""),
            "assignee": assignee_name,
            "type": (f.get("issuetype") or {}).get("name", ""),
        })
    # 断言解析层没读错外层：有条目时 key 必须非空（ai-delegation 规则 3）
    assert all(i["key"] for i in items), "jira 返回体解析异常：存在无 key 的条目"
    return items


def map_state(jira_status: str, table: dict[str, str]) -> str | None:
    """映射表外返回 None——调用方保留 story 状态并记一次告警，不猜。"""
    return table.get(jira_status)


def map_priority(jira_priority: str) -> int:
    return PRIORITY_MAP.get(jira_priority, 3)


@dataclass(frozen=True)
class SyncDecision:
    create: bool
    set_state: str | None  # None = 不动状态
    unmapped_status: bool


def sync_decision(*, existing: bool, prev_status: str | None, jira_status: str,
                  table: dict[str, str]) -> SyncDecision:
    """只在 Jira 状态相对上次同步变化时覆盖 story 状态；首次导入按映射置初态。"""
    mapped = map_state(jira_status, table)
    if not existing:
        return SyncDecision(create=True, set_state=mapped or STATE_SUBMITTED, unmapped_status=mapped is None)
    if prev_status == jira_status:
        return SyncDecision(create=False, set_state=None, unmapped_status=False)
    return SyncDecision(create=False, set_state=mapped, unmapped_status=mapped is None)


# ---------- 派发 ----------


@dataclass(frozen=True)
class LaunchSpec:
    worker_script: str
    repo_path: str
    issue_key: str
    dispatch_dir: str
    image: str
    model: str
    deliver: bool
    timeout_seconds: int
    env: dict[str, str]


def launch_cmd(spec: LaunchSpec) -> str:
    """在 master 节点上后台起 worker.sh，退出码落 <dispatch_dir>/rc，日志落 worker.log。

    用 setsid + nohup 脱离 docker exec 的会话：worker 一跑几个小时，openvort 重启不能把它带走。
    """
    if not is_issue_key(spec.issue_key):
        raise ValueError(f"issue_key 不合法: {spec.issue_key!r}")
    if not spec.repo_path.startswith("/"):
        raise ValueError("repo_path 必须是宿主上的绝对路径")
    env = {
        "AUTODEV_IMAGE": spec.image,
        "AUTODEV_MODEL": spec.model,
        "AUTODEV_DELIVER": "1" if spec.deliver else "0",
        "AUTODEV_TIMEOUT": str(int(spec.timeout_seconds)),
        **validate_env(spec.env),
    }
    env_part = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    d = shlex.quote(spec.dispatch_dir)
    inner = (
        f"env {env_part} {shlex.quote(spec.worker_script)} {shlex.quote(spec.issue_key)} "
        f"--repo {shlex.quote(spec.repo_path)} > {d}/worker.log 2>&1; echo $? > {d}/rc"
    )
    return (
        f"mkdir -p {d} || exit 2; if [ -e {d}/rc ]; then echo already-finished; exit 3; fi; "
        f"nohup setsid bash -c {shlex.quote(inner)} > /dev/null 2>&1 & "
        f"echo launched"
    )


def probe_cmd(dispatch_dir: str) -> str:
    """一次 exec 取回：rc（若已结束）+ worker.log 里的摘要/运行目录行。"""
    d = shlex.quote(dispatch_dir)
    return (
        f"if [ -f {d}/rc ]; then echo \"RC=$(cat {d}/rc)\"; else echo RC=; fi; "
        f"grep -E '^\\[worker\\] (摘要|运行目录|结果 rc=) ' {d}/worker.log 2>/dev/null; true"
    )


@dataclass(frozen=True)
class Probe:
    rc: int | None
    summary_path: str
    run_dir: str
    verdict_line: str


def parse_probe(text: str) -> Probe:
    rc: int | None = None
    summary_path = ""
    run_dir = ""
    verdict = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("RC="):
            v = line[3:].strip()
            rc = int(v) if v.lstrip("-").isdigit() else None
        elif line.startswith("[worker] 摘要 "):
            summary_path = line[len("[worker] 摘要 "):].strip()
        elif line.startswith("[worker] 运行目录 "):
            run_dir = line[len("[worker] 运行目录 "):].strip()
        elif line.startswith("[worker] 结果 rc="):
            verdict = line[len("[worker] "):]
    return Probe(rc=rc, summary_path=summary_path, run_dir=run_dir, verdict_line=verdict)


def summary_cmd(summary_path: str) -> str:
    return f"cat {shlex.quote(summary_path)}"


def parse_summary(text: str) -> dict:
    d = json.loads(text)
    assert isinstance(d, dict) and "ticket" in d, "summary.json 结构异常：缺 ticket"
    return d


def usage_cmd(usage_report: str, issue_key: str) -> str:
    return f"python3 {shlex.quote(usage_report)} --ticket {shlex.quote(issue_key)} --json"


def pick_usage(report_text: str, run_dir: str) -> dict | None:
    """usage-report --json 按轮次给出条目，run 字段 = $RUN 的目录名。"""
    rows = json.loads(report_text)
    if isinstance(rows, dict):
        rows = rows.get("runs") or rows.get("items") or []
    name = run_dir.rstrip("/").rsplit("/", 1)[-1]
    for r in rows:
        if r.get("run") == name:
            return r
    return None


def compute_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """按固定价目算费；模型不在价目表 → 0（只报 token）。缓存命中不单独计价。"""
    price = MODEL_PRICES.get(model)
    if not price:
        return 0.0
    return round(input_tokens / 1e6 * price[0] + output_tokens / 1e6 * price[1], 4)


# ---------- .env 三行合并 ----------


def env_read_cmd(env_path: str) -> str:
    return f"cat {shlex.quote(env_path)} 2>/dev/null; true"


def env_write_cmd(env_path: str) -> str:
    """内容走 stdin：`umask 077; cat > path; chmod 600 path`。"""
    p = shlex.quote(env_path)
    d = shlex.quote(env_path.rsplit("/", 1)[0])
    return f"umask 077 && mkdir -p {d} && cat > {p} && chmod 600 {p}"


def env_merge(existing: str, values: dict[str, str]) -> str | None:
    """只替换 HCM_BASE_URL / HCM_USERNAME / HCM_PASSWORD 三行，其余行（含 HCM_TOKEN）逐字保留。

    返回合并后的全文；与现有内容完全一致时返回 None（调用方不写、不动 mtime）。
    """
    missing = [k for k in HCM_ENV_KEYS if not (values.get(k) or "").strip()]
    if missing:
        raise ValueError("凭据缺项：" + ", ".join(missing))
    lines = existing.splitlines() if existing else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in HCM_ENV_KEYS:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    for k in HCM_ENV_KEYS:
        if k not in seen:
            out.append(f"{k}={values[k]}")
    merged = "\n".join(out) + "\n"
    if existing and merged == (existing if existing.endswith("\n") else existing + "\n"):
        return None
    return merged


def env_changed_keys(existing: str, values: dict[str, str]) -> list[str]:
    """日志用：哪些键的值变了（不输出值）。"""
    current: dict[str, str] = {}
    for line in (existing or "").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            current[k.strip()] = v
    return [k for k in HCM_ENV_KEYS if current.get(k) != values.get(k)]


# ---------- 闸门 ----------


@dataclass(frozen=True)
class GateInput:
    enabled: bool
    paused: bool
    node_max_slots: int
    node_running: int
    daily_cap: int
    started_today: int
    failure_threshold: int
    recent_outcomes: tuple[str, ...]  # 最近 N 次已结束运行的 outcome，新的在前


@dataclass(frozen=True)
class GateResult:
    allowed: int
    reason: str


def gate(inp: GateInput) -> GateResult:
    """按结果分支，不猜原因。allowed=0 时 reason 说明哪道门关的。"""
    if not inp.enabled:
        return GateResult(0, "项目未启用派发")
    if inp.paused:
        return GateResult(0, "派发已暂停")
    if inp.failure_threshold > 0 and len(inp.recent_outcomes) >= inp.failure_threshold:
        window = inp.recent_outcomes[: inp.failure_threshold]
        if all(o == OUTCOME_FAILED for o in window):
            return GateResult(0, f"熔断：最近 {inp.failure_threshold} 次运行全部失败，人工排查后恢复")
    slots = max(0, inp.node_max_slots - inp.node_running)
    if slots == 0:
        return GateResult(0, f"slot 已满（节点 running={inp.node_running}/max_slots={inp.node_max_slots}）")
    cap = max(0, inp.daily_cap - inp.started_today)
    if cap == 0:
        return GateResult(0, f"今日已达日上限 {inp.daily_cap}")
    return GateResult(min(slots, cap), "")


def node_max_slots(node_config: dict) -> int:
    try:
        return max(1, int(node_config.get("max_slots", 1)))
    except (TypeError, ValueError):
        return 1


def is_today(ts: datetime | None, today: date | None = None) -> bool:
    if ts is None:
        return False
    return ts.date() == (today or date.today())
