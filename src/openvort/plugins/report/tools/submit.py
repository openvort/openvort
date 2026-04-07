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
        "支持编辑草稿、提交、撤回已提交的汇报。"
    )

    def __init__(self, session_factory_getter, slot_getter=None):
        self._sf_getter = session_factory_getter
        self._slot_getter = slot_getter

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
                    "type": "string", "enum": ["daily", "weekly", "monthly", "quarterly"],
                    "description": "汇报类型",
                },
                "report_date": {"type": "string", "description": "汇报日期（YYYY-MM-DD），默认今天"},
                "title": {"type": "string", "description": "汇报标题"},
                "content": {"type": "string", "description": "汇报内容（Markdown）"},
                "publication_id": {"type": "string", "description": "关联的发布 ID"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        import json
        from openvort.plugins.report.service import ReportService

        action = params.get("action", "")
        service = ReportService(self._sf_getter())

        if action == "generate":
            result = await self._generate(service, params)
        elif action == "submit":
            result = await self._submit(service, params)
        elif action == "edit":
            result = await self._edit(service, params)
        elif action == "withdraw":
            result = await self._withdraw(service, params)
        else:
            result = {"ok": False, "error": f"未知操作: {action}"}
        return json.dumps(result, ensure_ascii=False, default=str)

    async def _generate(self, service, kwargs: dict) -> dict:
        report_type = kwargs.get("report_type", "daily")
        report_date_str = kwargs.get("report_date", "")
        reporter_name = kwargs.get("reporter_name", "")

        report_date = date.fromisoformat(report_date_str) if report_date_str else date.today()
        reporter_id = ""
        if reporter_name:
            reporter_id = await self._resolve_member_id(reporter_name)
            if not reporter_id:
                return {"ok": False, "error": f"未找到成员: {reporter_name}"}

        collected_data = await self._collect_data(reporter_id, reporter_name, report_type, report_date)
        title = self._build_title(report_type, report_date, reporter_name)
        content = self._build_content(report_type, collected_data)

        report = await service.create_report(
            reporter_id=reporter_id or "unknown",
            report_type=report_type, report_date=report_date,
            title=title, content=content, status="draft",
            auto_generated=True, publication_id=kwargs.get("publication_id"),
        )
        return {"ok": True, "report": report, "collected_data": collected_data,
                "message": "汇报草稿已生成，请确认或修改后提交"}

    async def _submit(self, service, kwargs: dict) -> dict:
        report_id = kwargs.get("report_id", "")
        if report_id:
            result = await service.update_report(report_id, status="submitted")
            if not result:
                return {"ok": False, "error": "汇报不存在"}
            return {"ok": True, "report": result, "message": "汇报已提交"}

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
            report_type=report_type, report_date=report_date,
            title=title, content=content, status="submitted",
            publication_id=kwargs.get("publication_id"),
        )
        return {"ok": True, "report": report, "message": "汇报已提交"}

    async def _edit(self, service, kwargs: dict) -> dict:
        report_id = kwargs.get("report_id", "")
        if not report_id:
            return {"ok": False, "error": "需要 report_id"}
        fields = {}
        for key in ("title", "content"):
            if key in kwargs:
                fields[key] = kwargs[key]
        result = await service.update_report(report_id, **fields)
        if not result:
            return {"ok": False, "error": "汇报不存在"}
        return {"ok": True, "report": result}

    async def _withdraw(self, service, kwargs: dict) -> dict:
        report_id = kwargs.get("report_id", "")
        if not report_id:
            return {"ok": False, "error": "需要 report_id"}
        report = await service.get_report(report_id)
        if not report:
            return {"ok": False, "error": "汇报不存在"}
        if report["status"] != "submitted":
            return {"ok": False, "error": f"当前状态 {report['status']} 不可撤回"}
        result = await service.update_report(report_id, status="draft")
        return {"ok": True, "report": result, "message": "汇报已撤回为草稿"}

    async def _resolve_member_id(self, name: str) -> str:
        from sqlalchemy import select
        from openvort.contacts.models import Member
        async with self._sf_getter()() as session:
            stmt = select(Member).where(Member.name == name).limit(1)
            result = await session.execute(stmt)
            member = result.scalar_one_or_none()
            return member.id if member else ""

    async def _collect_data(self, member_id: str, member_name: str, report_type: str, report_date: date) -> dict:
        data: dict = {"git": None, "vortflow": None}

        if report_type == "daily":
            since = until = report_date.isoformat()
        elif report_type == "weekly":
            start = report_date - timedelta(days=report_date.weekday())
            since, until = start.isoformat(), report_date.isoformat()
        elif report_type == "quarterly":
            qm = ((report_date.month - 1) // 3) * 3 + 1
            since, until = report_date.replace(month=qm, day=1).isoformat(), report_date.isoformat()
        else:
            since, until = report_date.replace(day=1).isoformat(), report_date.isoformat()

        try:
            from openvort.plugins.vortgit.tools.commits import WorkSummaryTool
            tool = WorkSummaryTool.__new__(WorkSummaryTool)
            tool._sf_getter = self._sf_getter
            result = await tool.execute(member_name=member_name or None, period="custom", since=since, until=until)
            if result.get("ok"):
                data["git"] = {
                    "total_commits": result.get("git", {}).get("total_commits", 0),
                    "active_repos": result.get("git", {}).get("active_repos", 0),
                    "repo_breakdown": result.get("git", {}).get("repo_breakdown", []),
                }
        except Exception as e:
            log.debug(f"采集 Git 数据失败: {e}")

        try:
            provider = self._slot_getter("project_provider") if self._slot_getter else None
            if provider:
                since_dt = datetime.combine(date.fromisoformat(since), datetime.min.time())
                until_dt = datetime.combine(date.fromisoformat(until), datetime.max.time())
                summary = await provider.get_tasks_summary(project_id="", member_id=member_id, since=since_dt, until=until_dt)
                data["vortflow"] = {"tasks_completed": summary.tasks_done, "bugs_fixed": summary.bugs_fixed}
        except Exception as e:
            log.debug(f"采集 VortFlow 数据失败: {e}")

        return data

    @staticmethod
    def _build_title(report_type: str, report_date: date, reporter_name: str) -> str:
        label = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报"}.get(report_type, "汇报")
        name_part = f"{reporter_name} " if reporter_name else ""
        return f"{name_part}{label} - {report_date.isoformat()}"

    @staticmethod
    def _build_content(report_type: str, collected_data: dict) -> str:
        lines = []
        label = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报"}.get(report_type, "汇报")
        lines.append(f"## {label}\n")

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

        lines.extend(["### 今日工作", "（请补充具体工作内容）\n",
                       "### 遇到的问题", "（如有阻塞项请说明）\n",
                       "### 明日计划", "（请补充明日工作计划）"])
        return "\n".join(lines)
