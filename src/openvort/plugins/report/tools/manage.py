"""
report_manage — 管理汇报发布（模板+规则合体）
"""

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.report.tools.manage")


class ReportManageTool(BaseTool):
    """管理汇报发布的全生命周期"""

    name = "report_manage"
    description = (
        "管理汇报发布。"
        "一个发布包含汇报的格式要求（标题、描述、类型）和规则设置（提交人、白名单、接收人、汇报方式、通知）。"
        "支持创建、更新、删除、列表、启停操作。"
    )

    def __init__(self, session_factory_getter):
        self._sf_getter = session_factory_getter

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "delete", "list", "get", "toggle"],
                    "description": "操作类型",
                },
                "publication_id": {"type": "string", "description": "发布 ID（更新/删除/启停时需要）"},
                "name": {"type": "string", "description": "发布名称"},
                "description": {"type": "string", "description": "描述"},
                "report_type": {
                    "type": "string", "enum": ["daily", "weekly", "monthly", "quarterly"],
                    "description": "汇报类型",
                },
                "repeat_cycle": {
                    "type": "string", "enum": ["daily", "weekly", "monthly"],
                    "description": "重复周期",
                },
                "deadline_time": {"type": "string", "description": "截止时间，如 '次日 10:00'"},
                "submitter_ids": {"type": "array", "items": {"type": "string"}, "description": "提交人 ID 列表"},
                "whitelist_ids": {"type": "array", "items": {"type": "string"}, "description": "白名单 ID 列表"},
                "receiver_ids": {"type": "array", "items": {"type": "string"}, "description": "接收人 ID 列表"},
                "enabled": {"type": "boolean", "description": "是否启用"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        import json
        from openvort.plugins.report.service import ReportService

        action = params.get("action", "")
        service = ReportService(self._sf_getter())

        if action == "create":
            name = params.get("name", "")
            if not name:
                return json.dumps({"ok": False, "error": "名称不能为空"}, ensure_ascii=False)
            result = await service.create_publication(
                name=name,
                description=params.get("description", ""),
                report_type=params.get("report_type", "daily"),
                repeat_cycle=params.get("repeat_cycle", "daily"),
                deadline_time=params.get("deadline_time", "次日 10:00"),
                submitter_ids=params.get("submitter_ids"),
                whitelist_ids=params.get("whitelist_ids"),
                receiver_ids=params.get("receiver_ids"),
            )
            return json.dumps({"ok": True, "publication": result}, ensure_ascii=False)

        elif action == "update":
            pub_id = params.get("publication_id", "")
            if not pub_id:
                return json.dumps({"ok": False, "error": "需要 publication_id"}, ensure_ascii=False)
            fields = {}
            for key in ("name", "description", "report_type", "repeat_cycle", "deadline_time",
                        "submitter_ids", "whitelist_ids", "receiver_ids", "enabled",
                        "reminder_enabled", "skip_weekends", "skip_holidays",
                        "allow_multiple", "allow_edit", "notify_summary", "notify_on_receive"):
                if key in params:
                    fields[key] = params[key]
            result = await service.update_publication(pub_id, **fields)
            if not result:
                return json.dumps({"ok": False, "error": "发布不存在"}, ensure_ascii=False)
            return json.dumps({"ok": True, "publication": result}, ensure_ascii=False)

        elif action == "delete":
            pub_id = params.get("publication_id", "")
            ok = await service.delete_publication(pub_id)
            return json.dumps({"ok": ok}, ensure_ascii=False)

        elif action == "list":
            pubs = await service.list_publications()
            return json.dumps({"ok": True, "publications": pubs, "count": len(pubs)}, ensure_ascii=False)

        elif action == "get":
            pub_id = params.get("publication_id", "")
            result = await service.get_publication(pub_id)
            if not result:
                return json.dumps({"ok": False, "error": "发布不存在"}, ensure_ascii=False)
            return json.dumps({"ok": True, "publication": result}, ensure_ascii=False)

        elif action == "toggle":
            pub_id = params.get("publication_id", "")
            enabled = params.get("enabled", True)
            result = await service.update_publication(pub_id, enabled=enabled)
            if not result:
                return json.dumps({"ok": False, "error": "发布不存在"}, ensure_ascii=False)
            return json.dumps({"ok": True, "publication": result}, ensure_ascii=False)

        return json.dumps({"ok": False, "error": f"未知操作: {action}"}, ensure_ascii=False)
