"""AutoDev service — Jira→story 投影、确定性派发器、运行回收器。

职责边界：
- 派发决策全在 contract.gate（机械闸门），不经 LLM。
- 一切对 master 节点的动作都是 `docker exec <master> sh -c ...`，master 是 RemoteNode(docker)。
- 通用密钥不经过本服务；每项目平台系统用户由本服务在派发前写成 master 上的 0600 文件。
- 写外部系统的只有 worker（Jira/GitLab 由 /req 收口）；本服务只写 OpenVort 自己的表。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.contacts.models import Member
from openvort.core.execution.docker_executor import DockerExecutor
from openvort.db.models import RemoteNode, ScheduleJob
from openvort.plugins.autodev import contract as ct
from openvort.plugins.autodev.models import AutodevProject, AutodevRun
from openvort.plugins.vortflow.models import FlowComment, FlowExternalMapping, FlowStory
from openvort.utils.logging import get_logger

log = get_logger("plugins.autodev.service")

PROJECT_FIELDS = (
    "repo_path", "jira_project_key", "sync_jql", "sync_max_results",
    "deliver", "enabled", "paused", "env_json", "hcm_base_url", "hcm_username",
)
# 超过这个时长仍没有 rc，判 lost（worker 自身 6h 超时 + 收口余量）
LOST_AFTER = timedelta(hours=9)
POLL_INTERVAL = 60
ACTION_DISPATCH = "autodev_dispatch"
ACTION_SYNC = "autodev_sync"
ENV_REL_PATH = "03_config/.env"
MASK = "****"


def _encrypt(plain: str) -> str:
    from openvort.plugins.vortgit.crypto import encrypt_token
    return encrypt_token(plain) if plain else ""


def _decrypt(enc: str) -> str:
    from openvort.plugins.vortgit.crypto import decrypt_token
    return decrypt_token(enc) if enc else ""


def mask(secret: str) -> str:
    return (MASK + secret[-4:]) if len(secret) > 4 else (MASK if secret else "")


class AutodevError(RuntimeError):
    pass


async def _default_write(container_id: str, command: str, content: str, timeout: int = 30) -> dict:
    """docker exec -i：内容走 stdin（凭据不进命令行、不进 env）。"""
    proc = await asyncio.create_subprocess_exec(
        "docker", "exec", "-i", container_id, "sh", "-c", command,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await asyncio.wait_for(proc.communicate(content.encode("utf-8")), timeout=timeout)
    return {"stdout": out.decode("utf-8", "replace"), "stderr": err.decode("utf-8", "replace"),
            "exit_code": proc.returncode}


class AutodevService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], exec_fn=None, write_fn=None):
        self._sf = session_factory
        # exec_fn(container_id, command, timeout=) -> {"stdout","stderr","exit_code"}；测试注入桩
        self._exec_fn = exec_fn or DockerExecutor._exec_streaming
        self._write_fn = write_fn or _default_write
        self._dispatch_lock = asyncio.Lock()
        self._poll_task: asyncio.Task | None = None
        self.ai_member_id: str = ""  # 全局唯一 AI 员工，插件配置注入
        # 数字员工快照，供插件配置下拉用；由后台循环刷新
        self.member_choices: list[dict] = []

    # ---------- master 节点 ----------

    async def master_node_id(self) -> str:
        """master = 全局 AI 员工绑定的工作机；不按项目配置。"""
        if not self.ai_member_id:
            raise AutodevError("未配置全局 AI 员工（插件配置 ai_member_id）")
        async with self._sf() as db:
            m = await db.get(Member, self.ai_member_id)
        if not m:
            raise AutodevError(f"AI 员工不存在: {self.ai_member_id}")
        if not m.remote_node_id:
            raise AutodevError(f"AI 员工「{m.name}」未绑定工作机（master）")
        return m.remote_node_id

    async def _node(self, node_id: str) -> tuple[str, dict]:
        if not node_id:
            raise AutodevError("未绑定 master 节点")
        async with self._sf() as db:
            node = await db.get(RemoteNode, node_id)
        if not node:
            raise AutodevError(f"master 节点不存在: {node_id}")
        if node.node_type != "docker":
            raise AutodevError(f"master 节点类型必须是 docker，当前 {node.node_type}")
        try:
            cfg = json.loads(node.config) if node.config else {}
        except Exception:
            cfg = {}
        cid = cfg.get("container_id", "")
        if not cid:
            raise AutodevError("master 节点未配置 container_id")
        return cid, cfg

    async def exec_on(self, node_id: str, command: str, timeout: int = 120) -> str:
        """在 master 上跑一条命令，非零退出直接抛错——不让「命令失败」与「空输出」同形。"""
        cid, _ = await self._node(node_id)
        result = await self._exec_fn(cid, command, timeout=timeout)
        if result["exit_code"] != 0:
            detail = (result.get("stderr") or result.get("stdout") or "")[:500]
            raise AutodevError(f"master 命令失败 rc={result['exit_code']}: {detail}")
        return result["stdout"]

    async def write_on(self, node_id: str, command: str, content: str) -> None:
        cid, _ = await self._node(node_id)
        result = await self._write_fn(cid, command, content)
        if result["exit_code"] != 0:
            detail = (result.get("stderr") or result.get("stdout") or "")[:500]
            raise AutodevError(f"master 写文件失败 rc={result['exit_code']}: {detail}")

    # ---------- 项目配置 ----------

    async def get_project(self, flow_project_id: str) -> AutodevProject | None:
        async with self._sf() as db:
            res = await db.execute(select(AutodevProject).where(AutodevProject.project_id == flow_project_id))
            return res.scalar_one_or_none()

    async def _project_or_raise(self, flow_project_id: str) -> AutodevProject:
        p = await self.get_project(flow_project_id)
        if not p:
            raise AutodevError("该项目尚未配置自动交付")
        return p

    async def upsert_project(self, flow_project_id: str, data: dict) -> AutodevProject:
        data = dict(data)
        if "env_json" in data:
            env = data["env_json"]
            if isinstance(env, str):
                env = json.loads(env or "{}")
            data["env_json"] = json.dumps(ct.validate_env(env), ensure_ascii=False)
        password = data.pop("hcm_password", None)
        async with self._sf() as db:
            res = await db.execute(select(AutodevProject).where(AutodevProject.project_id == flow_project_id))
            p = res.scalar_one_or_none()
            if not p:
                p = AutodevProject(project_id=flow_project_id)
                db.add(p)
            for k in PROJECT_FIELDS:
                if k in data and data[k] is not None:
                    setattr(p, k, data[k])
            # 以 **** 开头视为未修改（脱敏回显原样提交）
            if password is not None and not str(password).startswith(MASK):
                p.hcm_password_enc = _encrypt(str(password))
            await db.commit()
            await db.refresh(p)
            return p

    async def set_paused(self, flow_project_id: str, paused: bool) -> AutodevProject:
        return await self.upsert_project(flow_project_id, {"paused": paused})

    async def list_enabled_projects(self) -> list[AutodevProject]:
        async with self._sf() as db:
            res = await db.execute(
                select(AutodevProject).where(AutodevProject.enabled.is_(True))
                .order_by(AutodevProject.last_dispatched_at.asc().nulls_first(), AutodevProject.created_at.asc())
            )
            return list(res.scalars().all())

    def hcm_values(self, p: AutodevProject) -> dict[str, str]:
        return {
            "HCM_BASE_URL": p.hcm_base_url or "",
            "HCM_USERNAME": p.hcm_username or "",
            "HCM_PASSWORD": _decrypt(p.hcm_password_enc),
        }

    # ---------- Jira → story 投影 ----------

    async def sync_project(self, p: AutodevProject) -> dict:
        """一轮同步：经 master 列单 → 创建/更新 story + 映射。返回计数。Jira 是真相，本方法不写 Jira。"""
        text = await self.exec_on(
            await self.master_node_id(),
            ct.jira_sync_cmd(p.jira_project_key, p.sync_jql, p.sync_max_results), timeout=120,
        )
        issues = ct.parse_jira_issues(text)
        table = ct.STATUS_MAP
        counts = {"seen": len(issues), "created": 0, "updated": 0, "state_changed": 0, "unmapped": 0}
        if not issues:
            log.info(f"autodev sync {p.jira_project_key}: JQL 零命中，保留既有 story")
        async with self._sf() as db:
            for it in issues:
                m = (await db.execute(
                    select(FlowExternalMapping).where(
                        FlowExternalMapping.adapter == "jira",
                        FlowExternalMapping.local_type == "story",
                        FlowExternalMapping.external_id == it["key"],
                    )
                )).scalar_one_or_none()
                story = await db.get(FlowStory, m.local_id) if m else None
                if m and story and story.project_id != p.project_id:
                    # 同一 key 已投影到别的项目：不抢，记告警
                    log.warning(f"autodev sync: {it['key']} 已映射到项目 {story.project_id}，跳过")
                    continue
                decision = ct.sync_decision(
                    existing=bool(m and story), prev_status=(m.sync_cursor if m else None),
                    jira_status=it["status"], table=table,
                )
                if decision.unmapped_status:
                    counts["unmapped"] += 1
                    log.warning(f"autodev sync: Jira 状态「{it['status']}」不在映射表，{it['key']} 保留 story 状态")
                if decision.create:
                    story = FlowStory(
                        id=uuid.uuid4().hex, project_id=p.project_id, title=it["summary"] or it["key"],
                        description=it["description"], priority=ct.map_priority(it["priority"]),
                        state=decision.set_state or ct.STATE_SUBMITTED,
                    )
                    db.add(story)
                    if m:
                        m.local_id = story.id
                    else:
                        db.add(FlowExternalMapping(
                            local_type="story", local_id=story.id, adapter="jira", external_id=it["key"],
                            sync_cursor=it["status"], last_synced_at=datetime.now(),
                        ))
                    counts["created"] += 1
                else:
                    story.title = it["summary"] or story.title
                    story.description = it["description"]
                    story.priority = ct.map_priority(it["priority"])
                    if decision.set_state and story.state != decision.set_state:
                        story.state = decision.set_state
                        counts["state_changed"] += 1
                    counts["updated"] += 1
                if m:
                    m.sync_cursor = it["status"]
                    m.last_synced_at = datetime.now()
            proj = await db.get(AutodevProject, p.id)
            if proj:
                proj.last_synced_at = datetime.now()
            await db.commit()
        return counts

    async def sync_all(self) -> str:
        lines = []
        for p in await self.list_enabled_projects():
            try:
                c = await self.sync_project(p)
                lines.append(f"{p.jira_project_key}: 命中 {c['seen']} · 新建 {c['created']} · "
                             f"更新 {c['updated']} · 状态变更 {c['state_changed']} · 表外状态 {c['unmapped']}")
            except Exception as e:
                lines.append(f"{p.jira_project_key or p.project_id[:8]}: 同步失败 {e}")
        return "\n".join(lines) or "没有启用的项目"

    # ---------- 队列与闸门 ----------

    async def queue(self, p: AutodevProject) -> list[dict]:
        """可派 story：本项目 · dev_assign · 指派给全局 AI 员工 · 有 Jira 映射。"""
        if not self.ai_member_id:
            return []
        async with self._sf() as db:
            rows = (await db.execute(
                select(FlowStory, FlowExternalMapping.external_id)
                .join(FlowExternalMapping, (FlowExternalMapping.local_id == FlowStory.id)
                      & (FlowExternalMapping.local_type == "story") & (FlowExternalMapping.adapter == "jira"))
                .where(FlowStory.project_id == p.project_id, FlowStory.state == ct.STATE_DEV_ASSIGN,
                       FlowStory.assignee_id == self.ai_member_id, FlowStory.is_archived.is_(False))
                .order_by(FlowStory.priority.asc(), FlowStory.created_at.asc())
            )).all()
        return [{"story_id": s.id, "key": key, "title": s.title, "priority": s.priority} for s, key in rows]

    async def unmapped_dev_assign(self, p: AutodevProject) -> int:
        if not self.ai_member_id:
            return 0
        async with self._sf() as db:
            sub = select(FlowExternalMapping.local_id).where(
                FlowExternalMapping.local_type == "story", FlowExternalMapping.adapter == "jira")
            return int((await db.execute(
                select(func.count(FlowStory.id)).where(
                    FlowStory.project_id == p.project_id, FlowStory.state == ct.STATE_DEV_ASSIGN,
                    FlowStory.assignee_id == self.ai_member_id, FlowStory.id.not_in(sub))
            )).scalar() or 0)

    async def _running_total(self) -> int:
        """全部项目共用一台 master，slot 按全局 running 数算。"""
        async with self._sf() as db:
            stmt = select(func.count(AutodevRun.id)).where(AutodevRun.status == "running")
            return int((await db.execute(stmt)).scalar() or 0)

    async def _gate_input(self, p: AutodevProject) -> ct.GateInput:
        today_start = datetime.combine(datetime.now().date(), datetime.min.time())
        async with self._sf() as db:
            started_today = int((await db.execute(
                select(func.count(AutodevRun.id)).where(
                    AutodevRun.project_id == p.id, AutodevRun.started_at >= today_start
                )
            )).scalar() or 0)
            recent = (await db.execute(
                select(AutodevRun.outcome)
                .where(AutodevRun.project_id == p.id, AutodevRun.status != "running")
                .order_by(AutodevRun.started_at.desc())
                .limit(max(ct.FAILURE_THRESHOLD, 1))
            )).scalars().all()
        _, cfg = await self._node(await self.master_node_id())
        return ct.GateInput(
            enabled=p.enabled, paused=p.paused,
            node_max_slots=ct.node_max_slots(cfg), node_running=await self._running_total(),
            daily_cap=ct.DAILY_CAP, started_today=started_today,
            failure_threshold=ct.FAILURE_THRESHOLD, recent_outcomes=tuple(recent),
        )

    async def _running_keys(self, project_pk: str) -> set[str]:
        async with self._sf() as db:
            res = await db.execute(
                select(AutodevRun.issue_key).where(AutodevRun.project_id == project_pk, AutodevRun.status == "running")
            )
            return set(res.scalars().all())

    # ---------- 派发 ----------

    async def dispatch(self, flow_project_id: str, *, issue_key: str = "", max_starts: int = 1,
                       trigger: str = "manual") -> dict:
        """一个项目的一次派发：闸门 → 队列 → 起 worker。返回 {started, reason, text}。"""
        async with self._dispatch_lock:  # 单写者：同一时刻只有一个派发在决定起谁
            p = await self._project_or_raise(flow_project_id)
            return await self._dispatch_locked(p, issue_key=issue_key, max_starts=max_starts, trigger=trigger)

    async def _dispatch_locked(self, p: AutodevProject, *, issue_key: str, max_starts: int, trigger: str) -> dict:
        if not p.repo_path:
            raise AutodevError("repo_path 必须配置")
        await self.master_node_id()  # 员工未配 / 未绑机在这里就报，不走闸门
        missing = [k for k, v in self.hcm_values(p).items() if not v.strip()]
        if missing:
            reason = "凭据缺项：" + ", ".join(missing)
            return {"started": [], "reason": reason, "text": f"未派发：{reason}"}
        running = await self._running_keys(p.id)
        if issue_key and issue_key in running:  # 同单互斥先于其它闸门：理由要指向那张单
            return {"started": [], "reason": "该单已在运行", "text": f"未派发：{issue_key} 已在运行"}
        g = ct.gate(await self._gate_input(p))
        if g.allowed == 0:
            return {"started": [], "reason": g.reason, "text": f"未派发：{g.reason}"}
        budget = min(g.allowed, max(1, int(max_starts)))

        queue = await self.queue(p)
        if issue_key:
            picked = [q for q in queue if q["key"] == issue_key]
            if not picked:
                reason = f"{issue_key} 不在队列（需 dev_assign · 指派给 AI 员工 · 有 Jira 映射）"
                return {"started": [], "reason": reason, "text": f"未派发：{reason}"}
        else:
            picked = [q for q in queue if q["key"] not in running]
            if not picked:
                return {"started": [], "reason": "队列为空", "text": "未派发：队列为空（或队列里的单都已在运行）"}

        await self._materialize_env(p)
        started: list[str] = []
        for q in picked[:budget]:
            run = await self.start_run(p, q["key"], story_id=q["story_id"], trigger=trigger)
            started.append(run.issue_key)
        async with self._sf() as db:
            proj = await db.get(AutodevProject, p.id)
            proj.last_dispatched_at = datetime.now()
            await db.commit()
        return {"started": started, "reason": "", "text": "已派发：" + "、".join(started)}

    async def dispatch_all(self, *, max_starts: int = 1, trigger: str = "schedule") -> str:
        """全局派发：遍历启用项目，按 last_dispatched_at 轮转，每项目最多起 max_starts。"""
        async with self._dispatch_lock:
            lines = []
            for p in await self.list_enabled_projects():
                try:
                    r = await self._dispatch_locked(p, issue_key="", max_starts=max_starts, trigger=trigger)
                    lines.append(f"{p.jira_project_key or p.project_id[:8]}: {r['text']}")
                except Exception as e:
                    lines.append(f"{p.jira_project_key or p.project_id[:8]}: 派发失败 {e}")
            return "\n".join(lines) or "没有启用的项目"

    async def _materialize_env(self, p: AutodevProject) -> None:
        """把三项平台凭据写进 <仓>/03_config/.env：只改三行、保留 HCM_TOKEN、相同不写。"""
        path = f"{p.repo_path.rstrip('/')}/{ENV_REL_PATH}"
        node = await self.master_node_id()
        existing = await self.exec_on(node, ct.env_read_cmd(path), timeout=15)
        values = self.hcm_values(p)
        merged = ct.env_merge(existing, values)
        if merged is None:
            return
        await self.write_on(node, ct.env_write_cmd(path), merged)
        log.info(f"autodev: 覆盖 {path} 的 {ct.env_changed_keys(existing, values)}（项目 {p.jira_project_key}）")

    async def start_run(self, p: AutodevProject, issue_key: str, *, story_id: str = "", trigger: str) -> AutodevRun:
        run_id = uuid.uuid4().hex
        run = AutodevRun(id=run_id, project_id=p.id, issue_key=issue_key, story_id=story_id, trigger=trigger,
                         model=ct.MODEL, status="running")
        dispatch_dir = f"{ct.DISPATCH_ROOT}/{issue_key}-{time.strftime('%Y%m%d-%H%M%S')}-{run_id[:8]}"
        run.dispatch_dir = dispatch_dir
        spec = ct.LaunchSpec(
            worker_script=ct.WORKER_SCRIPT, repo_path=p.repo_path, issue_key=issue_key,
            dispatch_dir=dispatch_dir, image=ct.WORKER_IMAGE, model=ct.MODEL, deliver=p.deliver,
            timeout_seconds=ct.TIMEOUT_SECONDS, env=json.loads(p.env_json or "{}"),
        )
        # 先落库再起容器：起了没记比记了没起更糟（前者没人回收）
        async with self._sf() as db:
            db.add(run)
            if story_id:
                story = await db.get(FlowStory, story_id)
                if story:
                    story.state = ct.STATE_IN_PROGRESS
            await db.commit()
        try:
            out = await self.exec_on(await self.master_node_id(), ct.launch_cmd(spec), timeout=30)
            if "launched" not in out:
                raise AutodevError(f"启动输出异常: {out[:200]}")
        except Exception as e:
            await self._finalize(run_id, status="finished", exit_code=None, outcome=ct.OUTCOME_FAILED,
                                 error=f"启动失败: {e}")
            raise
        log.info(f"autodev 派发 {issue_key} → {dispatch_dir}")
        return run

    # ---------- 回收 ----------

    async def _finalize(self, run_id: str, **fields) -> None:
        async with self._sf() as db:
            run = await db.get(AutodevRun, run_id)
            if not run:
                return
            for k, v in fields.items():
                setattr(run, k, v)
            run.finished_at = datetime.now()
            await self._apply_story_outcome(db, run)
            await db.commit()

    async def _apply_story_outcome(self, db: AsyncSession, run: AutodevRun) -> None:
        """worker 结束后 story 的表内动作 + 系统评论。不写 Jira。"""
        if not run.story_id:
            return
        story = await db.get(FlowStory, run.story_id)
        if not story:
            return
        target = ct.OUTCOME_TO_STATE.get(run.outcome)
        if target:
            story.state = target
        if self.ai_member_id:
            text = f"[autodev] {run.issue_key} 运行结束：{run.outcome or '未知'} · 退出码 {run.exit_code} · " \
                   f"{ct.describe_exit(run.exit_code)}"
            if run.mr_url:
                text += f" · MR {run.mr_url}"
            if run.error:
                text += f" · {run.error}"
            text += f" · run {run.id[:8]}"
            db.add(FlowComment(entity_type="story", entity_id=story.id, author_id=self.ai_member_id, content=text))

    async def poll_once(self) -> int:
        """回收已结束的运行。返回本轮回收条数。"""
        async with self._sf() as db:
            rows = (await db.execute(
                select(AutodevRun, AutodevProject)
                .join(AutodevProject, AutodevProject.id == AutodevRun.project_id)
                .where(AutodevRun.status == "running")
            )).all()
        done = 0
        for run, p in rows:
            try:
                if await self._reconcile(run, p):
                    done += 1
            except Exception as e:
                log.warning(f"autodev 回收 {run.issue_key} 失败: {e}")
        return done

    async def _reconcile(self, run: AutodevRun, p: AutodevProject) -> bool:
        node = await self.master_node_id()
        probe = ct.parse_probe(await self.exec_on(node, ct.probe_cmd(run.dispatch_dir), timeout=30))
        if probe.rc is None:
            if datetime.now() - run.started_at > LOST_AFTER:
                await self._finalize(run.id, status="lost", outcome=ct.OUTCOME_FAILED,
                                     error=f"超过 {LOST_AFTER} 未回收到退出码")
                return True
            return False

        fields: dict = {
            "status": "finished", "exit_code": probe.rc, "outcome": ct.outcome_for(probe.rc),
            "verdict": probe.verdict_line or ct.describe_exit(probe.rc), "run_dir": probe.run_dir,
        }
        errors: list[str] = []
        if probe.summary_path:
            try:
                s = ct.parse_summary(await self.exec_on(node, ct.summary_cmd(probe.summary_path)))
                fields.update({
                    "branch": s.get("branch") or "", "worktree": s.get("worktree") or "",
                    "mr_url": s.get("mr_url") or "", "image_id": s.get("image_id") or "",
                    "model": s.get("model") or run.model,
                })
                if s.get("verdict"):
                    fields["verdict"] = s["verdict"]
            except Exception as e:
                errors.append(f"summary.json 读取失败: {e}")
        else:
            errors.append("摘要缺失：worker.log 里没有摘要行")
        run_dir = fields.get("run_dir") or ""
        if run_dir:
            try:
                usage = ct.pick_usage(
                    await self.exec_on(node, ct.usage_cmd(ct.USAGE_REPORT, run.issue_key), timeout=60),
                    run_dir,
                )
                if usage:
                    fields.update({
                        "input_tokens": int(usage.get("inputTokens") or 0),
                        "output_tokens": int(usage.get("outputTokens") or 0),
                        "total_tokens": int(usage.get("totalTokens") or 0),
                        "cached_tokens": int(usage.get("cachedInputTokens") or 0),
                        "calls": int(usage.get("calls") or 0),
                        "duration_ms": int(usage.get("durMs") or 0),
                    })
                    fields["cost"] = ct.compute_cost(
                        fields["input_tokens"], fields["output_tokens"], fields.get("model") or run.model
                    )
                else:
                    errors.append("用量缺失：usage-report 里没有本次运行目录的条目")
            except Exception as e:
                errors.append(f"用量读取失败: {e}")
        else:
            errors.append("用量缺失：未取到运行目录")
        if errors:
            fields["error"] = "; ".join(errors)
        await self._finalize(run.id, **fields)
        log.info(f"autodev 回收 {run.issue_key} rc={probe.rc} outcome={fields['outcome']}")
        return True

    def start_background(self) -> None:
        if self._poll_task is not None:
            return

        async def loop():
            while True:
                try:
                    await self.poll_once()
                except Exception as e:
                    log.warning(f"autodev poll 异常: {e}")
                try:
                    await self.refresh_member_choices()
                except Exception as e:
                    log.warning(f"autodev 刷新员工列表异常: {e}")
                await asyncio.sleep(POLL_INTERVAL)

        self._poll_task = asyncio.get_running_loop().create_task(loop())

    async def refresh_member_choices(self) -> list[dict]:
        """把可选的数字员工刷进快照。插件配置表单是同步的、取不到 DB，只能读这份快照。"""
        async with self._sf() as db:
            rows = (await db.execute(
                select(Member).where(Member.is_virtual.is_(True)).order_by(Member.name)
            )).scalars().all()
        self.member_choices = [
            {"id": m.id, "name": m.name, "node_id": m.remote_node_id or ""} for m in rows
        ]
        return self.member_choices

    # ---------- 查询 ----------

    async def list_runs(self, flow_project_id: str, *, issue_key: str = "", limit: int = 50) -> list[AutodevRun]:
        p = await self.get_project(flow_project_id)
        if not p:
            return []
        async with self._sf() as db:
            stmt = select(AutodevRun).where(AutodevRun.project_id == p.id)
            if issue_key:
                stmt = stmt.where(AutodevRun.issue_key == issue_key)
            stmt = stmt.order_by(AutodevRun.started_at.desc()).limit(limit)
            return list((await db.execute(stmt)).scalars().all())

    async def stats(self, flow_project_id: str, *, days: int = 7) -> dict:
        p = await self.get_project(flow_project_id)
        if not p:
            return {"configured": False}
        since = datetime.now() - timedelta(days=days)
        async with self._sf() as db:
            rows = (await db.execute(
                select(AutodevRun).where(AutodevRun.project_id == p.id, AutodevRun.started_at >= since)
            )).scalars().all()
        by_outcome: dict[str, int] = {}
        for r in rows:
            k = r.outcome or ("running" if r.status == "running" else "unknown")
            by_outcome[k] = by_outcome.get(k, 0) + 1
        finished = [r for r in rows if r.status != "running"]
        running_keys = await self._running_keys(p.id)
        queue = await self.queue(p)
        result = {
            "configured": True,
            "days": days,
            "runs": len(rows),
            "running": sum(1 for r in rows if r.status == "running"),
            "by_outcome": by_outcome,
            "tickets": len({r.issue_key for r in rows}),
            "delivered_tickets": len({r.issue_key for r in rows if r.outcome == ct.OUTCOME_DELIVERED}),
            "total_tokens": sum(r.total_tokens for r in finished),
            "input_tokens": sum(r.input_tokens for r in finished),
            "output_tokens": sum(r.output_tokens for r in finished),
            "cost": round(sum(r.cost for r in finished), 4),
            "priced": ct.MODEL in ct.MODEL_PRICES,
            "queue": len([q for q in queue if q["key"] not in running_keys]),
            "queue_unmapped": await self.unmapped_dev_assign(p),
            "last_synced_at": p.last_synced_at.isoformat() if p.last_synced_at else None,
            "gate": None,
        }
        try:
            g = ct.gate(await self._gate_input(p))
            result["gate"] = {"allowed": g.allowed, "reason": g.reason}
        except AutodevError as e:
            result["gate"] = {"allowed": 0, "reason": str(e)}
        return result

    # ---------- 全局定时任务（复用 ScheduleJob） ----------

    async def find_global_job(self, action_type: str) -> ScheduleJob | None:
        async with self._sf() as db:
            return (await db.execute(
                select(ScheduleJob).where(ScheduleJob.action_type == action_type).order_by(ScheduleJob.id.asc())
            )).scalars().first()

    async def ensure_global_jobs(self, *, creator_id: str = "") -> list[dict]:
        """两条全局任务（派发 / 同步）按需创建，禁用态；重复调用不重复创建。owner = 全局 AI 员工。"""
        from openvort.web.deps import get_schedule_service

        svc = get_schedule_service()
        if svc is None:
            raise AutodevError("ScheduleService 未初始化")
        if not self.ai_member_id:
            raise AutodevError("未配置全局 AI 员工（插件配置 ai_member_id）")
        out = []
        specs = [
            (ACTION_DISPATCH, "自动交付 · 派发", "每隔固定时间遍历启用项目，按机械闸门派发 worker（不经 LLM）", 300,
             {"max_starts": 1}),
            (ACTION_SYNC, "自动交付 · Jira 同步", "把各项目的 Jira 工单单向投影为 story（不写 Jira）", 600, {}),
        ]
        for action, name, desc, interval, cfg in specs:
            job = await self.find_global_job(action)
            if job:
                out.append(svc._job_to_dict(job))
                continue
            created = await svc.create_job(
                owner_id=self.ai_member_id, creator_id=creator_id or self.ai_member_id, name=name,
                description=desc, schedule_type="interval", schedule=str(interval), scope="team",
                action_type=action, action_config=cfg, enabled=False, visible=True,
                target_member_id=self.ai_member_id,
            )
            out.append(created)
        return out

    async def set_global_job(self, action_type: str, *, enabled: bool, interval_seconds: int | None = None) -> dict:
        from openvort.web.deps import get_schedule_service

        svc = get_schedule_service()
        if svc is None:
            raise AutodevError("ScheduleService 未初始化")
        job = await self.find_global_job(action_type)
        if not job:
            await self.ensure_global_jobs()
            job = await self.find_global_job(action_type)
        fields: dict = {"enabled": enabled}
        if interval_seconds:
            fields.update(schedule_type="interval", schedule=str(int(interval_seconds)))
        updated = await svc.update_job(job.job_id, is_admin=True, **fields)
        if not updated:
            raise AutodevError("更新全局任务失败")
        return updated


# 全局单例：plugin 在 activate 时创建，router / tools / schedule handler 共用
_service: AutodevService | None = None


def set_service(svc: AutodevService) -> None:
    global _service
    _service = svc


def get_service() -> AutodevService:
    if _service is None:
        raise AutodevError("AutodevService 未初始化")
    return _service


async def schedule_dispatch_handler(job, config: dict) -> str:
    """ScheduleJob action_type=autodev_dispatch：全局确定性派发，不经 agent。"""
    return await get_service().dispatch_all(max_starts=int((config or {}).get("max_starts", 1)), trigger="schedule")


async def schedule_sync_handler(job, config: dict) -> str:
    """ScheduleJob action_type=autodev_sync：全局 Jira → story 投影。"""
    return await get_service().sync_all()
