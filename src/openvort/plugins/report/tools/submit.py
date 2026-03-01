"""
report_submit — 提交/生成/编辑汇报
"""

from datetime import date, datetime, timedelta

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.tools.submit")


class ReportSubmitTool(BaseTool):
    """提交、生成、编辑汇报"""

    name = "report_submit"
    description = (
        "提交汇报（日报/周报/月报）。"
        "支持手动提交内容，也可以通过 generate 自动从 Git 提交和 VortFlow 任务数据生成汇报草稿。"
        "支持编辑草稿、提交给审阅人、撤回已提交的汇报。"
    )

    def __init__(self, session_factory_getter):
        self._sf_getter = session_factory_getter

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["generate", "submit", "edit", "withdraw"],
                    "description": "操作：generate 自动生成草稿，submit 提交汇报，edit 编辑草稿，withdraw 撤回",
                },
                "report_id": {"type": "string", "description": "汇报 ID（submit/edit/withdraw 时需要）"},
                "reporter_name": {"type": "string", "description": "汇报人姓名（generate 时用于匹配 member）"},
                "report_type": {
                    "type": "string", "enum": ["daily", "weekly", "monthly"],
                    "description": "汇报类型",
                },
                "report_date": {"type": "string", "description": "汇报日期（YYYY-MM-DD），默认今天"},
                "title": {"type": "string", "description": "汇报标题"},
                "content": {"type": "string", "description": "汇报内容（Markdown）"},
                "reviewer_id": {"type": "string", "description": "审阅人 member_id"},
                "template_id": {"type": "string", "description": "使用的模板 ID"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> dict:
        from openvort.plugins.report.service import ReportService

        action = kwargs.get("action", "")
        service = ReportService(self._sf_getter())

        if action == "generate":
            return await self._generate(service, kwargs)
        elif action == "submit":
            return await self._submit(service, kwargs)
        elif action == "edit":
            return await self._edit(service, kwargs)
        elif action == "withdraw":
            return await self._withdraw(service, kwargs)
        return {"ok": False, "error": f"未知操作: {action}"}

    async def _generate(self, service, kwargs: dict) -> dict:
        """AI 自动生成汇报草稿"""
        report_type = kwargs.get("report_type", "daily")
        report_date_str = kwargs.get("report_date", "")
        reporter_name = kwargs.get("reporter_name", "")

        report_date = date.fromisoformat(report_date_str) if report_date_str else date.today()

        reporter_id = ""
        if reporter_name:
            reporter_id = await self._resolve_member_id(reporter_name)
            if not reporter_id:
                return {"ok": False, "error": f"未找到成员: {reporter_name}"}

        # Collect data from VortGit and VortFlow
        collected_data = await self._collect_data(reporter_id, reporter_name, report_type, report_date)

        # Build draft content
        title = self._build_title(report_type, report_date, reporter_name)
        content = self._build_content(report_type, collected_data)

        report = await service.create_report(
            reporter_id=reporter_id or "unknown",
            report_type=report_type,
            report_date=report_date,
            title=title,
            content=content,
            status="draft",
            auto_generated=True,
            template_id=kwargs.get("template_id"),
            reviewer_id=kwargs.get("reviewer_id"),
        )

        return {
            "ok": True,
            "report": report,
            "collected_data": collected_data,
            "message": "汇报草稿已生成，请确认或修改后提交",
        }

    async def _submit(self, service, kwargs: dict) -> dict:
        """提交汇报"""
        report_id = kwargs.get("report_id", "")

        if report_id:
            result = await service.update_report(report_id, status="submitted")
            if not result:
                return {"ok": False, "error": "汇报不存在"}
            return {"ok": True, "report": result, "message": "汇报已提交"}

        # Direct submit without existing draft
        report_type = kwargs.get("report_type", "daily")
        report_date_str = kwargs.get("report_date", "")
        report_date = date.fromisoformat(report_date_str) if report_date_str else date.today()
        reporter_name = kwargs.get("reporter_name", "")
        reporter_id = ""
        if reporter_name:
            reporter_id = await self._resolve_member_id(reporter_name) or ""

        content = kwargs.get("content", "")
        title = kwargs.get("title", "") or self._build_title(report_type, report_date, reporter_name)

        if not content:
            return {"ok": False, "error": "汇报内容不能为空"}

        report = await service.create_report(
            reporter_id=reporter_id or "unknown",
            report_type=report_type,
            report_date=report_date,
            title=title,
            content=content,
            status="submitted",
            reviewer_id=kwargs.get("reviewer_id"),
            template_id=kwargs.get("template_id"),
        )
        return {"ok": True, "report": report, "message": "汇报已提交"}

    async def _edit(self, service, kwargs: dict) -> dict:
        """编辑汇报草稿"""
        report_id = kwargs.get("report_id", "")
        if not report_id:
            return {"ok": False, "error": "需要 report_id"}

        fields = {}
        for key in ("title", "content", "reviewer_id"):
            if key in kwargs:
                fields[key] = kwargs[key]

        result = await service.update_report(report_id, **fields)
        if not result:
            return {"ok": False, "error": "汇报不存在"}
        return {"ok": True, "report": result}

    async def _withdraw(self, service, kwargs: dict) -> dict:
        """撤回已提交的汇报"""
        report_id = kwargs.get("report_id", "")
        if not report_id:
            return {"ok": False, "error": "需要 report_id"}

        report = await service.get_report(report_id)
        if not report:
            return {"ok": False, "error": "汇报不存在"}
        if report["status"] not in ("submitted",):
            return {"ok": False, "error": f"当前状态 {report['status']} 不可撤回"}

        result = await service.update_report(report_id, status="draft")
        return {"ok": True, "report": result, "message": "汇报已撤回为草稿"}

    async def _resolve_member_id(self, name: str) -> str:
        """通过姓名查找 member_id"""
        from sqlalchemy import select
        from openvort.contacts.models import Member

        async with self._sf_getter()() as session:
            stmt = select(Member).where(Member.name == name).limit(1)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            return member.id if member else ""

    async def _collect_data(self, member_id: str, member_name: str, report_type: str, report_date: date) -> dict:
        """从 VortGit 和 VortFlow 采集数据"""
        data: dict = {"git": None, "vortflow": None}

        if report_type == "daily":
            since = report_date.isoformat()
            until = report_date.isoformat()
        elif report_type == "weekly":
            start = report_date - timedelta(days=report_date.weekday())
            since = start.isoformat()
            until = report_date.isoformat()
        else:
            since = report_date.replace(day=1).isoformat()
            until = report_date.isoformat()

        # Try VortGit commits
        try:
            from openvort.plugins.vortgit.tools.commits import WorkSummaryTool
            tool = WorkSummaryTool.__new__(WorkSummaryTool)
            tool._sf_getter = self._sf_getter
            result = await tool.execute(
                member_name=member_name or None,
                period="custom",
                since=since,
                until=until,
            )
            if result.get("ok"):
                data["git"] = {
                    "total_commits": result.get("git", {}).get("total_commits", 0),
                    "active_repos": result.get("git", {}).get("active_repos", 0),
                    "repo_breakdown": result.get("git", {}).get("repo_breakdown", []),
                }
        except Exception as e:
            log.debug(f"采集 Git 数据失败: {e}")

        # Try VortFlow tasks
        try:
            from sqlalchemy import select, func as sa_func
            from openvort.plugins.vortflow.models import FlowTask, FlowBug

            async with self._sf_getter()() as session:
                tasks_done = 0
                bugs_fixed = 0

                if member_id:
                    stmt = select(sa_func.count(FlowTask.id)).where(
                        FlowTask.assignee_id == member_id,
                        FlowTask.state.in_(["done", "closed"]),
                    )
                    result = await session.execute(stmt)
                    tasks_done = result.scalar() or 0

                    stmt = select(sa_func.count(FlowBug.id)).where(
                        FlowBug.assignee_id == member_id,
                        FlowBug.state.in_(["resolved", "closed"]),
                    )
                    result = await session.execute(stmt)
                    bugs_fixed = result.scalar() or 0

                data["vortflow"] = {
                    "tasks_completed": tasks_done,
                    "bugs_fixed": bugs_fixed,
                }
        except Exception as e:
            log.debug(f"采集 VortFlow 数据失败: {e}")

        return data

    @staticmethod
    def _build_title(report_type: str, report_date: date, reporter_name: str) -> str:
        type_label = {"daily": "日报", "weekly": "周报", "monthly": "月报"}.get(report_type, "汇报")
        name_part = f"{reporter_name} " if reporter_name else ""
        return f"{name_part}{type_label} - {report_date.isoformat()}"

    @staticmethod
    def _build_content(report_type: str, collected_data: dict) -> str:
        lines = []
        type_label = {"daily": "日报", "weekly": "周报", "monthly": "月报"}.get(report_type, "汇报")
        lines.append(f"## {type_label}\n")

        git = collected_data.get("git")
        if git:
            lines.append("### 代码提交")
            lines.append(f"- 总提交数：{git.get('total_commits', 0)}")
            lines.append(f"- 活跃仓库：{git.get('active_repos', 0)}")
            for repo in git.get("repo_breakdown", [])[:5]:
                lines.append(f"  - {repo.get('repo', 'N/A')}: {repo.get('commits', 0)} 次提交")
            lines.append("")

        vf = collected_data.get("vortflow")
        if vf:
            lines.append("### 任务进度")
            lines.append(f"- 完成任务：{vf.get('tasks_completed', 0)}")
            lines.append(f"- 修复 Bug：{vf.get('bugs_fixed', 0)}")
            lines.append("")

        lines.append("### 今日工作")
        lines.append("（请补充具体工作内容）\n")
        lines.append("### 遇到的问题")
        lines.append("（如有阻塞项请说明）\n")
        lines.append("### 明日计划")
        lines.append("（请补充明日工作计划）")

        return "\n".join(lines)
