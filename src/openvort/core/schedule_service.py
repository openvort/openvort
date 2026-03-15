"""
定时任务业务层

连接 DB 持久化和 APScheduler 调度器，提供 CRUD + 执行逻辑。
"""

import json
import uuid
from datetime import datetime, timedelta
from functools import partial

from sqlalchemy import select, delete, func as sa_func, and_

from openvort.contacts.service import ContactService
from openvort.core.scheduler import Scheduler
from openvort.db.models import ScheduleJob
from openvort.utils.logging import get_logger

log = get_logger("core.schedule_service")


class ScheduleService:
    """定时任务管理服务"""

    def __init__(self, session_factory, scheduler: Scheduler, agent_runtime=None, notify_fn=None):
        """
        Args:
            notify_fn: async (owner_id, job_name, result_text) -> None
                       Callback to deliver execution result to the job owner.
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
        job = ScheduleJob(
            job_id=job_id,
            name=name,
            description=description,
            owner_id=owner_id,
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

        log.info(f"创建任务: {job_id} ({name})")
        return self._job_to_dict(job)

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
            if not is_admin and job.owner_id != owner_id:
                return None

            for key in ("name", "description", "schedule_type", "schedule", "timezone", "action_type", "enabled", "visible", "target_member_id"):
                if key in fields:
                    setattr(job, key, fields[key])
            if "action_config" in fields:
                job.action_config = json.dumps(fields["action_config"])

            await session.commit()
            await session.refresh(job)

        # 重新注册到调度器
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
            if not is_admin and job.owner_id != owner_id:
                return False

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
                if not is_admin and job.owner_id != owner_id:
                    continue
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
                base = base.where(ScheduleJob.owner_id == owner_id)
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
            if not is_admin and job.owner_id != owner_id:
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
                # Skip once-type tasks that already ran
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
        """构建执行人上下文（AI 员工或系统默认）"""
        from openvort.core.context import RequestContext
        from openvort.auth.service import AuthService

        exec_id = f"{job.job_id}_{uuid.uuid4().hex[:8]}"

        # 如果绑定了 AI 员工，使用完整的成员上下文
        if job.target_member_id:
            member = await self._contacts_service.get_member(job.target_member_id)
            if member:
                # 获取成员的角色和权限
                roles = []
                permissions = set()
                try:
                    auth_service = AuthService(self._session_factory)
                    roles = await auth_service.get_member_roles(member.id)
                    permissions = await auth_service.get_member_permissions(member.id)
                except Exception as e:
                    log.warning(f"获取成员角色权限失败: {e}")

                ctx = RequestContext(
                    channel="scheduler",
                    user_id=exec_id,
                    member=member,
                    roles=roles,
                    permissions=permissions,
                )
                return ctx

        # 否则使用默认上下文（系统助手）
        return RequestContext(
            channel="scheduler",
            user_id=exec_id,
            member=None,
        )

    async def _execute_job(self, job: ScheduleJob) -> str:
        """执行任务 — 目前只支持 agent_chat"""
        config = json.loads(job.action_config) if job.action_config else {}
        prompt = config.get("prompt", "")
        if not prompt:
            raise ValueError("action_config 缺少 prompt")

        # Resolve owner name for context
        owner_name = ""
        try:
            owner = await self._contacts_service.get_member(job.owner_id)
            if owner:
                owner_name = owner.name
        except Exception:
            pass

        # 构建执行人上下文（自动注入 AI 员工人设）
        ctx = await self._build_executor_context(job)

        # 根据执行人类型生成上下文提示
        executor_name = ""
        if ctx.member and ctx.member.is_virtual:
            executor_name = ctx.member.name or "AI 员工"
        else:
            executor_name = "系统助手"

        sched_context = (
            f"[系统] 你正在执行定时任务「{job.name}」，任务创建者是{owner_name or job.owner_id}。"
            f"当前执行人是{executor_name}。"
            f"请根据任务要求执行操作，如需发送消息请通过 wecom_send_message 等工具发送给创建者。\n\n"
            f"任务要求：{prompt}"
        )

        result_text = ""
        status = "success"

        # Push task_status: executing
        try:
            from openvort.web.ws import manager as _ws
            executor_id = ctx.member.id if ctx.member else ""
            if executor_id:
                await _ws.send_to(job.owner_id, {
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
            # Push task_status: idle
            try:
                from openvort.web.ws import manager as _ws
                executor_id = ctx.member.id if ctx.member else ""
                if executor_id:
                    await _ws.send_to(job.owner_id, {
                        "type": "task_status",
                        "member_id": executor_id,
                        "status": "idle",
                        "job_name": "",
                    })
            except Exception:
                pass

        # 更新执行状态
        async with self._session_factory() as session:
            stmt = select(ScheduleJob).where(ScheduleJob.job_id == job.job_id)
            res = await session.execute(stmt)
            db_job = res.scalar_one_or_none()
            if db_job:
                db_job.last_run_at = datetime.now()
                db_job.last_status = status
                db_job.last_result = result_text[:2000]
                await session.commit()

        # 调用通知回调（如果有）
        if self._notify_fn:
            try:
                await self._notify_fn(
                    owner_id=job.owner_id,
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
            self._scheduler.add_once(job.job_id, callback, run_at)

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
