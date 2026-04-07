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

        vf = collected_data.get("vortflow")
        git = collected_data.get("git")
        has_system_data = bool(
            (vf and vf.get("has_data"))
            or (git and git.get("total_commits", 0) > 0)
        )

        if has_system_data:
            message = "已根据工作记录生成日报草稿，请确认或告诉我需要修改的地方。确认后我会帮你提交。"
        else:
            message = (
                "暂未找到今天的系统工作记录。"
                "请告诉我你今天主要做了哪些工作，我来帮你整理成日报。"
            )

        return {
            "ok": True, "report": report,
            "collected_data": collected_data,
            "has_system_data": has_system_data,
            "message": message,
        }

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

    @staticmethod
    def _resolve_date_range(report_type: str, report_date: date) -> tuple[str, str]:
        if report_type == "daily":
            return report_date.isoformat(), report_date.isoformat()
        elif report_type == "weekly":
            start = report_date - timedelta(days=report_date.weekday())
            return start.isoformat(), report_date.isoformat()
        elif report_type == "quarterly":
            qm = ((report_date.month - 1) // 3) * 3 + 1
            return report_date.replace(month=qm, day=1).isoformat(), report_date.isoformat()
        else:
            return report_date.replace(day=1).isoformat(), report_date.isoformat()

    async def _collect_data(self, member_id: str, member_name: str, report_type: str, report_date: date) -> dict:
        import json as _json

        data: dict = {"git": None, "vortflow": None}
        since, until = self._resolve_date_range(report_type, report_date)

        try:
            from openvort.plugins.vortgit.tools.commits import WorkSummaryTool
            tool = WorkSummaryTool.__new__(WorkSummaryTool)
            result_str = await tool.execute({
                "member_name": member_name or "",
                "period": "custom",
                "since": since,
                "until": until,
            })
            result = _json.loads(result_str) if isinstance(result_str, str) else result_str
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
            if provider and member_id:
                since_dt = datetime.combine(date.fromisoformat(since), datetime.min.time())
                until_dt = datetime.combine(date.fromisoformat(until), datetime.max.time())
                if hasattr(provider, "get_member_daily_details"):
                    data["vortflow"] = await provider.get_member_daily_details(
                        member_id, since_dt, until_dt,
                    )
                else:
                    summary = await provider.get_tasks_summary(
                        project_id="", member_id=member_id,
                        since=since_dt, until=until_dt,
                    )
                    data["vortflow"] = {
                        "has_data": (summary.tasks_done + summary.bugs_fixed) > 0,
                        "tasks_completed": [],
                        "bugs_fixed": [],
                        "tasks_in_progress": [],
                        "stories_in_progress": [],
                        "events": [],
                        "summary": {
                            "tasks_completed_count": summary.tasks_done,
                            "bugs_fixed_count": summary.bugs_fixed,
                        },
                    }
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
        lines: list[str] = []
        label = {"daily": "日报", "weekly": "周报", "monthly": "月报", "quarterly": "季报"}.get(report_type, "汇报")

        vf = collected_data.get("vortflow")
        has_vf_details = vf and vf.get("has_data") and vf.get("tasks_completed")
        git = collected_data.get("git")
        has_git = git and git.get("total_commits", 0) > 0

        if has_vf_details:
            tasks = vf.get("tasks_completed", [])
            if tasks:
                lines.append("### 完成的任务")
                for t in tasks:
                    proj = f"[{t['project_name']}] " if t.get("project_name") else ""
                    lines.append(f"- {proj}{t['title']}")
                lines.append("")

            bugs = vf.get("bugs_fixed", [])
            if bugs:
                lines.append("### 修复的缺陷")
                for b in bugs:
                    proj = f"[{b['project_name']}] " if b.get("project_name") else ""
                    sev = f"（{b['severity']}）" if b.get("severity") else ""
                    lines.append(f"- {proj}{b['title']}{sev}")
                lines.append("")

            doing = vf.get("tasks_in_progress", [])
            if doing:
                lines.append("### 进行中的任务")
                for t in doing:
                    proj = f"[{t['project_name']}] " if t.get("project_name") else ""
                    progress = f"（进度 {t['progress']}%）" if t.get("progress") else ""
                    lines.append(f"- {proj}{t['title']}{progress}")
                lines.append("")

            stories = vf.get("stories_in_progress", [])
            if stories:
                lines.append("### 进行中的需求")
                for s in stories:
                    proj = f"[{s['project_name']}] " if s.get("project_name") else ""
                    lines.append(f"- {proj}{s['title']}")
                lines.append("")

        elif vf and vf.get("has_data"):
            summary = vf.get("summary", {})
            if summary.get("tasks_completed_count") or summary.get("bugs_fixed_count"):
                lines.append("### 任务进度")
                lines.append(f"- 完成任务：{summary.get('tasks_completed_count', 0)}")
                lines.append(f"- 修复缺陷：{summary.get('bugs_fixed_count', 0)}")
                lines.append("")

        if has_git:
            lines.append("### 代码提交")
            lines.append(f"- 共 {git['total_commits']} 次提交，涉及 {git['active_repos']} 个仓库")
            for repo in git.get("repo_breakdown", [])[:5]:
                lines.append(f"  - {repo.get('repo', 'N/A')}: {repo.get('commits', 0)} 次提交")
            lines.append("")

        if not has_vf_details and not has_git:
            lines.append("### 今日工作")
            lines.append("（暂未采集到系统工作数据，请手动补充具体工作内容）\n")

        lines.append("### 遇到的问题")
        lines.append("（如有阻塞项请说明）\n")
        lines.append("### 明日计划")
        lines.append("（请补充明日工作计划）")

        return "\n".join(lines)
