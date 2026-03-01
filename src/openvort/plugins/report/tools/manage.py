"""
report_manage — 管理汇报模板和规则
"""

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.tools.manage")


class ReportManageTool(BaseTool):
    """管理汇报模板和规则的全生命周期"""

    name = "report_manage"
    description = (
        "管理汇报模板和汇报规则。"
        "模板定义汇报的格式和内容要求（如日报、周报、月报）。"
        "规则定义谁需要提交什么汇报、截止时间、审阅人等。"
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
                    "enum": [
                        "create_template", "update_template", "delete_template", "list_templates",
                        "create_rule", "update_rule", "delete_rule", "list_rules",
                    ],
                    "description": "操作类型",
                },
                "template_id": {"type": "string", "description": "模板 ID（更新/删除/创建规则时需要）"},
                "rule_id": {"type": "string", "description": "规则 ID（更新/删除规则时需要）"},
                "name": {"type": "string", "description": "模板名称（创建/更新模板时）"},
                "report_type": {
                    "type": "string", "enum": ["daily", "weekly", "monthly"],
                    "description": "汇报类型",
                },
                "content_schema": {
                    "type": "object",
                    "description": "模板内容结构（JSON，定义必填字段和格式要求）",
                },
                "auto_collect": {
                    "type": "object",
                    "description": "自动采集配置，如 {\"git\": true, \"vortflow\": true}",
                },
                "scope": {
                    "type": "string", "enum": ["member", "department"],
                    "description": "规则范围：member（个人）或 department（部门）",
                },
                "target_id": {"type": "string", "description": "规则目标（member_id 或 department_id）"},
                "reviewer_id": {"type": "string", "description": "审阅人 member_id"},
                "deadline_cron": {"type": "string", "description": "截止时间 cron 表达式（5段式）"},
                "reminder_minutes": {"type": "integer", "description": "提前提醒分钟数"},
                "escalation_minutes": {"type": "integer", "description": "超时升级通知分钟数"},
                "enabled": {"type": "boolean", "description": "是否启用"},
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs) -> dict:
        from openvort.plugins.report.service import ReportService

        action = kwargs.get("action", "")
        service = ReportService(self._sf_getter())

        if action == "create_template":
            name = kwargs.get("name", "")
            report_type = kwargs.get("report_type", "daily")
            if not name:
                return {"ok": False, "error": "模板名称不能为空"}
            result = await service.create_template(
                name=name,
                report_type=report_type,
                content_schema=kwargs.get("content_schema"),
                auto_collect=kwargs.get("auto_collect"),
            )
            return {"ok": True, "template": result}

        elif action == "update_template":
            template_id = kwargs.get("template_id", "")
            if not template_id:
                return {"ok": False, "error": "需要 template_id"}
            fields = {}
            for key in ("name", "report_type", "content_schema", "auto_collect"):
                if key in kwargs:
                    fields[key] = kwargs[key]
            result = await service.update_template(template_id, **fields)
            if not result:
                return {"ok": False, "error": "模板不存在"}
            return {"ok": True, "template": result}

        elif action == "delete_template":
            template_id = kwargs.get("template_id", "")
            ok = await service.delete_template(template_id)
            return {"ok": ok, "error": "" if ok else "模板不存在或删除失败"}

        elif action == "list_templates":
            templates = await service.list_templates()
            return {"ok": True, "templates": templates, "count": len(templates)}

        elif action == "create_rule":
            template_id = kwargs.get("template_id", "")
            scope = kwargs.get("scope", "member")
            target_id = kwargs.get("target_id", "")
            if not template_id or not target_id:
                return {"ok": False, "error": "需要 template_id 和 target_id"}
            result = await service.create_rule(
                template_id=template_id,
                scope=scope,
                target_id=target_id,
                reviewer_id=kwargs.get("reviewer_id"),
                deadline_cron=kwargs.get("deadline_cron", "0 18 * * 1-5"),
                reminder_minutes=kwargs.get("reminder_minutes", 30),
                escalation_minutes=kwargs.get("escalation_minutes", 120),
                enabled=kwargs.get("enabled", True),
            )
            return {"ok": True, "rule": result}

        elif action == "update_rule":
            rule_id = kwargs.get("rule_id", "")
            if not rule_id:
                return {"ok": False, "error": "需要 rule_id"}
            fields = {}
            for key in ("scope", "target_id", "reviewer_id", "deadline_cron",
                        "reminder_minutes", "escalation_minutes", "enabled"):
                if key in kwargs:
                    fields[key] = kwargs[key]
            result = await service.update_rule(rule_id, **fields)
            if not result:
                return {"ok": False, "error": "规则不存在"}
            return {"ok": True, "rule": result}

        elif action == "delete_rule":
            rule_id = kwargs.get("rule_id", "")
            ok = await service.delete_rule(rule_id)
            return {"ok": ok, "error": "" if ok else "规则不存在或删除失败"}

        elif action == "list_rules":
            rules = await service.list_rules(template_id=kwargs.get("template_id"))
            return {"ok": True, "rules": rules, "count": len(rules)}

        return {"ok": False, "error": f"未知操作: {action}"}
