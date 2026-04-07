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
        "规则定义哪些成员需要提交什么汇报、截止时间、审阅人等。"
        "一条规则可以关联多个成员。"
    )

    def __init__(self, session_factory_getter):
        self._sf_getter = session_factory_getter

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
                "name": {"type": "string", "description": "模板或规则名称"},
                "description": {"type": "string", "description": "模板描述（说明此汇报要提交的内容）"},
                "report_type": {
                    "type": "string", "enum": ["daily", "weekly", "monthly", "quarterly"],
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
                "member_ids": {
                    "type": "array", "items": {"type": "string"},
                    "description": "规则关联的成员 ID 列表",
                },
                "reviewer_id": {"type": "string", "description": "审阅人 member_id"},
                "deadline_cron": {"type": "string", "description": "截止时间 cron 表达式（5段式）"},
                "workdays_only": {"type": "boolean", "description": "是否仅工作日执行"},
                "reminder_minutes": {"type": "integer", "description": "提前提醒分钟数"},
                "escalation_minutes": {"type": "integer", "description": "超时升级通知分钟数"},
                "enabled": {"type": "boolean", "description": "是否启用"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        import json
        from openvort.plugins.report.service import ReportService

        action = params.get("action", "")
        service = ReportService(self._sf_getter())

        if action == "create_template":
            name = params.get("name", "")
            report_type = params.get("report_type", "daily")
            if not name:
                return json.dumps({"ok": False, "error": "模板名称不能为空"}, ensure_ascii=False)
            result = await service.create_template(
                name=name,
                description=params.get("description", ""),
                report_type=report_type,
                content_schema=params.get("content_schema"),
                auto_collect=params.get("auto_collect"),
            )
            return json.dumps({"ok": True, "template": result}, ensure_ascii=False)

        elif action == "update_template":
            template_id = params.get("template_id", "")
            if not template_id:
                return json.dumps({"ok": False, "error": "需要 template_id"}, ensure_ascii=False)
            fields = {}
            for key in ("name", "description", "report_type", "content_schema", "auto_collect"):
                if key in params:
                    fields[key] = params[key]
            result = await service.update_template(template_id, **fields)
            if not result:
                return json.dumps({"ok": False, "error": "模板不存在"}, ensure_ascii=False)
            return json.dumps({"ok": True, "template": result}, ensure_ascii=False)

        elif action == "delete_template":
            template_id = params.get("template_id", "")
            ok = await service.delete_template(template_id)
            return json.dumps({"ok": ok, "error": "" if ok else "模板不存在或删除失败"}, ensure_ascii=False)

        elif action == "list_templates":
            templates = await service.list_templates()
            return json.dumps({"ok": True, "templates": templates, "count": len(templates)}, ensure_ascii=False)

        elif action == "create_rule":
            template_id = params.get("template_id", "")
            member_ids = params.get("member_ids", [])
            if not template_id:
                return json.dumps({"ok": False, "error": "需要 template_id"}, ensure_ascii=False)
            if not member_ids:
                return json.dumps({"ok": False, "error": "需要 member_ids"}, ensure_ascii=False)
            result = await service.create_rule(
                template_id=template_id,
                member_ids=member_ids,
                name=params.get("name", ""),
                reviewer_id=params.get("reviewer_id"),
                deadline_cron=params.get("deadline_cron", "0 18 * * 1-5"),
                workdays_only=params.get("workdays_only", True),
                reminder_minutes=params.get("reminder_minutes", 30),
                escalation_minutes=params.get("escalation_minutes", 120),
                enabled=params.get("enabled", True),
            )
            return json.dumps({"ok": True, "rule": result}, ensure_ascii=False)

        elif action == "update_rule":
            rule_id = params.get("rule_id", "")
            if not rule_id:
                return json.dumps({"ok": False, "error": "需要 rule_id"}, ensure_ascii=False)
            fields = {}
            for key in ("name", "member_ids", "reviewer_id", "deadline_cron",
                        "workdays_only", "reminder_minutes", "escalation_minutes", "enabled"):
                if key in params:
                    fields[key] = params[key]
            result = await service.update_rule(rule_id, **fields)
            if not result:
                return json.dumps({"ok": False, "error": "规则不存在"}, ensure_ascii=False)
            return json.dumps({"ok": True, "rule": result}, ensure_ascii=False)

        elif action == "delete_rule":
            rule_id = params.get("rule_id", "")
            ok = await service.delete_rule(rule_id)
            return json.dumps({"ok": ok, "error": "" if ok else "规则不存在或删除失败"}, ensure_ascii=False)

        elif action == "list_rules":
            rules = await service.list_rules(template_id=params.get("template_id"))
            return json.dumps({"ok": True, "rules": rules, "count": len(rules)}, ensure_ascii=False)

        return json.dumps({"ok": False, "error": f"未知操作: {action}"}, ensure_ascii=False)
