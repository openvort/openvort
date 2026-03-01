"""
Report plugin — AI-driven enterprise reporting management.
"""

from pathlib import Path

from openvort.plugin.base import BasePlugin, BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report")


class ReportPlugin(BasePlugin):
    """汇报管理插件 — 企业日报/周报/月报自动生成与分发"""

    name = "report"
    display_name = "汇报管理"
    description = "通过 AI 对话管理汇报模板、规则，自动生成日报/周报/月报，支持催报和向上聚合"
    version = "0.1.0"

    def get_tools(self) -> list[BaseTool]:
        from openvort.db.engine import get_session_factory
        from openvort.plugins.report.tools.manage import ReportManageTool
        from openvort.plugins.report.tools.query import ReportQueryTool
        from openvort.plugins.report.tools.submit import ReportSubmitTool

        sf_getter = get_session_factory
        return [
            ReportManageTool(sf_getter),
            ReportSubmitTool(sf_getter),
            ReportQueryTool(sf_getter),
        ]

    def get_api_router(self):
        from openvort.plugins.report.router import router
        return router

    def get_permissions(self) -> list[dict]:
        return [
            {"code": "report.manage", "display_name": "管理汇报模板和规则"},
            {"code": "report.submit", "display_name": "提交汇报"},
            {"code": "report.review", "display_name": "审阅下属汇报"},
        ]

    def get_prompts(self) -> list[str]:
        prompts_dir = Path(__file__).parent / "prompts"
        prompts = []
        for f in sorted(prompts_dir.glob("*.md")):
            try:
                prompts.append(f.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning(f"读取 prompt 文件 {f.name} 失败: {e}")
        return prompts

    def validate_credentials(self) -> bool:
        return True
