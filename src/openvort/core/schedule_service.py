"""
定时任务业务层

连接 DB 持久化和 APScheduler 调度器，提供 CRUD + 执行逻辑。

owner_id = task owner (AI employee when delegated, user for personal reminders)
creator_id = who created/delegated this task (always the real human user)
"""

import json
import uuid
from datetime import datetime, timedelta
from functools import partial

from sqlalchemy import select, delete, or_, func as sa_func, and_

from openvort.contacts.service import ContactService
from openvort.core.scheduler import Scheduler
from openvort.db.models import ScheduleJob, WorkAssignment
from openvort.utils.logging import get_logger

log = get_logger("core.schedule_service")


class ScheduleService:
    """定时任务管理服务"""

    def __init__(self, session_factory, scheduler: Scheduler, agent_runtime=None, notify_fn=None):
        """
        Args:
            notify_fn: async (creator_id, job_name, result_text, ...) -> None
                       Callback to deliver execution result to the task creator.
        """
        self._session_factory = session_factory
        self._scheduler = scheduler
        self._agent = agent_runtime
        self._contacts_service = ContactService(session_factory)
        self._notify_fn = notify_fn

    # ---- CRUD ----

    async def create_job(
        self,
        owner_id: str,
        name: str,
        schedule_type: str,
        schedule: str,
        creator_id: str = "",
        scope: str = "personal",
        description: str = "",
        timezone: str = "Asia/Shanghai",
        action_type: str = "agent_chat",
        action_config: dict | None = None,
        enabled: bool = True,
        visible: bool = True,
        target_member_id: str = "",
    ) -> dict:
        job_id = f"sched_{uuid.uuid4().hex[:12]}"

        if not creator_id:
            creator_id = owner_id

        # Convert relative seconds to absolute ISO for once-type tasks
        if schedule_type == "once" and schedule.strip().isdigit():
            run_at = datetime.now() + timedelta(seconds=int(schedule.strip()))
            schedule = run_at.isoformat()

        job = ScheduleJob(
            job_id=job_id,
            name=name,
            description=description,
            owner_id=owner_id,
            creator_id=creator_id,
            scope=scope,
            schedule_type=schedule_type,
            schedule=schedule,
            timezone=timezone,
            action_type=action_type,
            action_config=json.dumps(action_config or {}),
            enabled=enabled,
            visible=visible,
            target_member_id=target_member_id,
        )
        async with self._session_factory() as session:
            session.add(job)
            await session.commit()
            await session.refresh(job)

        if enabled:
            self._register_job(job)

        # Auto-create WorkAssignment when delegated to AI employee
        is_delegated = owner_id != creator_id
        if is_delegated:
            try:
                await self._create_work_assignment(job)
            except Exception as e:
                log.warning(f"自动创建工作安排失败: {e}")

        log.info(f"创建任务: {job_id} ({name})")
        return self._job_to_dict(job)

    def _has_permission(self, job: ScheduleJob, member_id: str | None, is_admin: bool) -> bool:
        """Check if member has permission to manage this job."""
        if is_admin:
            return True
        if not member_id:
            return False
        return job.owner_id == member_id or job.creator_id == member_id

    async def _delete_linked_work_assignments(self, session, job: ScheduleJob) -> None:
        """Delete work assignments automatically created for a schedule."""
        await session.execute(
            delete(WorkAssignment).where(
                or_(
                    and_(
                        WorkAssignment.source_type == "schedule",
                        WorkAssignment.source_id == job.job_id,
                    ),
                    WorkAssignment.related_schedule_id == job.id,
                )
            )
        )

    async def update_job(
        self,
        job_id: str,
        owner_id: str | None = None,
        is_admin: bool = False,
        **fields,
    ) -> dict | None:
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                return None
            if not self._has_permission(job, owner_id, is_admin):
                return None

            for key in ("name", "description", "schedule_type", "schedule", "timezone", "action_type", "enabled", "visible"):
                if key in fields:
                    setattr(job, key, fields[key])
            if "action_config" in fields:
                job.action_config = json.dumps(fields["action_config"])

            await session.commit()
            await session.refresh(job)

        self._scheduler.remove(job_id)
        if job.enabled:
            self._register_job(job)

        log.info(f"更新任务: {job_id}")
        return self._job_to_dict(job)

    async def delete_job(self, job_id: str, owner_id: str | None = None, is_admin: bool = False) -> bool:
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                return False
            if not self._has_permission(job, owner_id, is_admin):
                return False

            await self._delete_linked_work_assignments(session, job)
            await session.execute(delete(ScheduleJob).where(ScheduleJob.job_id == job_id))
            await session.commit()

        self._scheduler.remove(job_id)
        log.info(f"删除任务: {job_id}")
        return True

    async def batch_delete_jobs(
        self, job_ids: list[str], owner_id: str | None = None, is_admin: bool = False
    ) -> int:
        count = 0
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id.in_(job_ids))
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            for job in jobs:
                if not self._has_permission(job, owner_id, is_admin):
                    continue
                await self._delete_linked_work_assignments(session, job)
                await session.execute(
                    delete(ScheduleJob).where(ScheduleJob.job_id == job.job_id)
                )
                self._scheduler.remove(job.job_id)
                count += 1
            await session.commit()
        log.info(f"批量删除 {count} 个任务")
        return count

    async def list_jobs(
        self,
        owner_id: str | None = None,
        scope: str | None = None,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        schedule_type: str | None = None,
        last_status: str | None = None,
        hide_done_once: bool = True,
    ) -> dict:
        async with self._session_factory() as session:
            base = select(ScheduleJob)
            if owner_id:
                # Show jobs owned by this member OR created by this member
                base = base.where(
                    or_(ScheduleJob.owner_id == owner_id, ScheduleJob.creator_id == owner_id)
                )
            if scope:
                base = base.where(ScheduleJob.scope == scope)
            if keyword:
                base = base.where(ScheduleJob.name.ilike(f"%{keyword}%"))
            if schedule_type:
                base = base.where(ScheduleJob.schedule_type == schedule_type)
            if last_status:
                base = base.where(ScheduleJob.last_status == last_status)
            if hide_done_once:
                base = base.where(
                    ~and_(
                        ScheduleJob.schedule_type == "once",
                        ScheduleJob.last_run_at.isnot(None),
                    )
                )

            count_result = await session.execute(
                select(sa_func.count()).select_from(base.subquery())
            )
            total = count_result.scalar() or 0

            stmt = base.order_by(ScheduleJob.created_at.desc())
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            return {"items": [self._job_to_dict(j) for j in jobs], "total": total}

    async def get_job(self, job_id: str) -> dict | None:
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            return self._job_to_dict(job) if job else None

    async def toggle_job(self, job_id: str, owner_id: str | None = None, is_admin: bool = False) -> dict | None:
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                return None
            if not self._has_permission(job, owner_id, is_admin):
                return None

            job.enabled = not job.enabled
            await session.commit()
            await session.refresh(job)

        if job.enabled:
            self._register_job(job)
        else:
            self._scheduler.remove(job_id)

        log.info(f"切换任务 {job_id} -> {'启用' if job.enabled else '禁用'}")
        return self._job_to_dict(job)

    async def run_now(self, job_id: str) -> dict:
        """手动立即执行一次"""
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                return {"success": False, "error": "任务不存在"}

        try:
            result_text = await self._execute_job(job)
            return {"success": True, "result": result_text}
        except Exception as e:
            log.error(f"手动执行任务 {job_id} 失败: {e}")
            return {"success": False, "error": str(e)}

    async def sync_to_scheduler(self) -> int:
        """启动时从 DB 恢复所有 enabled 的任务到 APScheduler"""
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.enabled == True)  # noqa: E712
            result = await session.execute(stmt)
            jobs = result.scalars().all()

            count = 0
            for job in jobs:
                if job.schedule_type == "once" and job.last_run_at is not None:
                    log.debug(f"跳过已执行的一次性任务: {job.job_id}")
                    continue
                try:
                    self._register_job(job)
                    count += 1
                except Exception as e:
                    log.error(f"恢复任务 {job.job_id} 失败: {e}")

        log.info(f"从 DB 恢复了 {count} 个定时任务")
        return count

    # ---- 内部方法 ----

    async def _build_executor_context(self, job: ScheduleJob) -> "RequestContext":
        """Build execution context. owner_id IS the executor (AI employee or system)."""
        from openvort.core.context import RequestContext
        from openvort.auth.service import AuthService

        exec_id = f"{job.job_id}_{uuid.uuid4().hex[:8]}"

        member = await self._contacts_service.get_member(job.owner_id)
        if member and member.is_virtual:
            roles = []
            permissions = set()
            try:
                auth_service = AuthService(self._session_factory)
                roles = await auth_service.get_member_roles(member.id)
                permissions = await auth_service.get_member_permissions(member.id)
            except Exception as e:
                log.warning(f"获取成员角色权限失败: {e}")

            return RequestContext(
                channel="scheduler",
                user_id=exec_id,
                member=member,
                roles=roles,
                permissions=permissions,
            )

        return RequestContext(
            channel="scheduler",
            user_id=exec_id,
            member=None,
        )

    def _get_notify_target(self, job: ScheduleJob) -> str:
        """Determine who should receive the execution notification."""
        if job.creator_id and job.creator_id != job.owner_id:
            return job.creator_id
        return job.owner_id

    async def _execute_job(self, job: ScheduleJob) -> str:
        """执行任务 — 目前只支持 agent_chat"""
        config = json.loads(job.action_config) if job.action_config else {}
        prompt = config.get("prompt", "")
        if not prompt:
            raise ValueError("action_config 缺少 prompt")

        notify_target = self._get_notify_target(job)

        # Resolve creator name for context
        creator_name = ""
        try:
            creator = await self._contacts_service.get_member(job.creator_id or job.owner_id)
            if creator:
                creator_name = creator.name
        except Exception:
            pass

        ctx = await self._build_executor_context(job)

        executor_name = ""
        if ctx.member and ctx.member.is_virtual:
            executor_name = ctx.member.name or "AI 员工"
        else:
            executor_name = "系统助手"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sched_context = (
            f"[系统] 你正在执行定时任务「{job.name}」，任务委派人是{creator_name or notify_target}。"
            f"当前执行人是{executor_name}。当前执行时间：{now_str}。"
            f"请直接执行任务并输出结果，不需要通过 IM 工具发送消息，系统会自动将结果通知委派人。\n\n"
            f"任务要求：{prompt}"
        )

        result_text = ""
        status = "success"

        # Push task_status: executing (to the creator, not the AI employee)
        try:
            from openvort.web.ws import manager as _ws
            executor_id = ctx.member.id if ctx.member else ""
            if executor_id:
                await _ws.send_to(notify_target, {
                    "type": "task_status",
                    "member_id": executor_id,
                    "status": "executing",
                    "job_name": job.name,
                })
        except Exception:
            pass

        try:
            if self._agent and job.action_type == "agent_chat":
                result_text = await self._agent.process(ctx, sched_context)
            else:
                result_text = "Agent 未初始化或不支持的 action_type"
                status = "failed"
        except Exception as e:
            result_text = str(e)
            status = "failed"
            log.error(f"执行任务 {job.job_id} 失败: {e}")
        finally:
            try:
                from openvort.web.ws import manager as _ws
                executor_id = ctx.member.id if ctx.member else ""
                if executor_id:
                    await _ws.send_to(notify_target, {
                        "type": "task_status",
                        "member_id": executor_id,
                        "status": "idle",
                        "job_name": "",
                    })
            except Exception:
                pass

        # 更新执行状态 + 同步工作安排
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job.job_id)
            res = await session.execute(stmt)
            db_job = res.scalar_one_or_none()
            if db_job:
                db_job.last_run_at = datetime.now()
                db_job.last_status = status
                db_job.last_result = result_text[:2000]

                try:
                    wa_stmt = select(WorkAssignment).where(
                        WorkAssignment.source_type == "schedule",
                        WorkAssignment.source_id == job.job_id,
                    )
                    wa = (await session.execute(wa_stmt)).scalar_one_or_none()
                    if wa:
                        wa.last_action_at = datetime.now()
                        if job.schedule_type == "once":
                            wa.status = "completed" if status == "success" else "pending"
                except Exception as e:
                    log.debug(f"更新工作安排状态失败: {e}")

                await session.commit()

        # Notify the creator (not the AI employee owner)
        if self._notify_fn:
            try:
                await self._notify_fn(
                    owner_id=notify_target,
                    job_name=job.name,
                    result_text=result_text,
                    executor_member=ctx.member,
                    job_id=job.job_id,
                    status=status,
                )
            except Exception as e:
                log.error(f"通知任务结果失败: {e}")

        return result_text

    def _register_job(self, job: ScheduleJob) -> None:
        """将 DB 任务注册到 APScheduler"""
        callback = partial(self._job_callback, job.job_id)

        if job.schedule_type == "cron":
            self._scheduler.add_cron(job.job_id, callback, job.schedule, timezone=job.timezone)
        elif job.schedule_type == "interval":
            self._scheduler.add_interval(job.job_id, callback, int(job.schedule))
        elif job.schedule_type == "once":
            schedule_val = job.schedule.strip()
            if schedule_val.isdigit():
                run_at = datetime.now() + timedelta(seconds=int(schedule_val))
            else:
                run_at = datetime.fromisoformat(schedule_val)
                if run_at <= datetime.now():
                    log.info(f"一次性任务 {job.job_id} 调度时间已过 ({schedule_val})，将立即执行")
                    run_at = datetime.now() + timedelta(seconds=2)
            self._scheduler.add_once(job.job_id, callback, run_at)

    async def _create_work_assignment(self, job: ScheduleJob) -> None:
        """Create a WorkAssignment record linked to the schedule job."""
        config = json.loads(job.action_config) if job.action_config else {}
        prompt = config.get("prompt", "")
        sched_desc = {
            "cron": f"cron: {job.schedule}",
            "interval": f"每 {job.schedule} 秒",
            "once": f"一次性: {job.schedule}",
        }.get(job.schedule_type, job.schedule)

        status = "ongoing" if job.schedule_type in ("cron", "interval") else "pending"

        async with self._session_factory() as session:
            wa = WorkAssignment(
                title=job.name,
                summary=job.description or prompt[:200],
                plan=sched_desc,
                requested_by_member_id=job.creator_id,
                assignee_member_id=job.owner_id,
                source_type="schedule",
                source_id=job.job_id,
                source_detail=prompt[:500],
                related_schedule_id=job.id,
                status=status,
                priority="normal",
            )
            session.add(wa)
            await session.commit()
        log.info(f"已为定时任务 {job.job_id} 创建工作安排")

    async def _job_callback(self, job_id: str) -> None:
        """APScheduler 回调 — 从 DB 加载最新任务并执行"""
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job_id)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                log.warning(f"回调时任务 {job_id} 不存在")
                return

        await self._execute_job(job)

    @staticmethod
    def _job_to_dict(job: ScheduleJob) -> dict:
        config = {}
        try:
            config = json.loads(job.action_config) if job.action_config else {}
        except Exception:
            pass
        return {
            "id": job.id,
            "job_id": job.job_id,
            "name": job.name,
            "description": job.description or "",
            "owner_id": job.owner_id,
            "creator_id": job.creator_id or "",
            "scope": job.scope,
            "schedule_type": job.schedule_type,
            "schedule": job.schedule,
            "timezone": job.timezone or "Asia/Shanghai",
            "action_type": job.action_type,
            "action_config": config,
            "target_member_id": job.target_member_id or "",
            "enabled": job.enabled,
            "visible": job.visible,
            "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
            "last_status": job.last_status or "pending",
            "last_result": job.last_result or "",
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
