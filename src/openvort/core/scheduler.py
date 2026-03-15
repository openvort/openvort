"""
定时任务调度器

基于 APScheduler，支持 cron 表达式、间隔执行和一次性定时任务。
"""

from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from openvort.utils.logging import get_logger

log = get_logger("core.scheduler")


class Scheduler:
    """定时任务调度器"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def add_cron(self, job_id: str, func, cron_expr: str, **kwargs) -> None:
        """添加 cron 任务

        Args:
            job_id: 任务 ID
            func: 异步函数
            cron_expr: 5-field (分 时 日 月 周) or 6-field (秒 分 时 日 月 周)
        """
        parts = cron_expr.split()
        cron_kwargs: dict = {}

        if len(parts) == 6:
            log.info(f"检测到 6 段 cron 表达式，首段作为秒字段: {cron_expr}")
            cron_kwargs = dict(
                second=parts[0], minute=parts[1], hour=parts[2],
                day=parts[3], month=parts[4], day_of_week=parts[5],
            )
        elif len(parts) == 5:
            cron_kwargs = dict(
                minute=parts[0], hour=parts[1],
                day=parts[2], month=parts[3], day_of_week=parts[4],
            )
        else:
            log.error(f"无效的 cron 表达式: {cron_expr}")
            return

        self._scheduler.add_job(
            func,
            "cron",
            id=job_id,
            replace_existing=True,
            **cron_kwargs,
            **kwargs,
        )
        log.info(f"已添加 cron 任务: {job_id} ({cron_expr})")

    def add_interval(self, job_id: str, func, seconds: int, **kwargs) -> None:
        """添加间隔任务"""
        self._scheduler.add_job(
            func,
            "interval",
            id=job_id,
            seconds=seconds,
            replace_existing=True,
            **kwargs,
        )
        log.info(f"已添加间隔任务: {job_id} (每 {seconds}s)")

    def add_once(self, job_id: str, func, run_at: datetime, **kwargs) -> None:
        """添加一次性定时任务

        Args:
            job_id: 任务 ID
            func: 异步函数
            run_at: 执行时间（datetime）
        """
        kwargs.setdefault("misfire_grace_time", 3600)
        self._scheduler.add_job(
            func,
            "date",
            id=job_id,
            run_date=run_at,
            replace_existing=True,
            **kwargs,
        )
        log.info(f"已添加一次性任务: {job_id} ({run_at})")

    def remove(self, job_id: str) -> None:
        """移除任务"""
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def start(self) -> None:
        """启动调度器"""
        if not self._scheduler.running:
            self._scheduler.start()
            log.info("调度器已启动")

    def stop(self) -> None:
        """停止调度器"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("调度器已停止")

    def list_jobs(self) -> list[dict]:
        """列出所有任务"""
        return [
            {"id": job.id, "next_run": str(job.next_run_time), "trigger": str(job.trigger)}
            for job in self._scheduler.get_jobs()
        ]
