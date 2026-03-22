"""查询个人待办任务"""

import json
from datetime import datetime, date

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB


def _json_serial(obj):
    """JSON 序列化辅助"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


class MyTasksTool(BaseTool):
    name = "zentao_my_tasks"
    description = "查询指定人员在禅道中的待办任务列表"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "人员账号（禅道 UserID）"},
                "status": {"type": "string", "description": "筛选状态（可选）",
                           "enum": ["wait", "doing", "all"], "default": "all"},
            },
            "required": ["account"],
        }

    async def execute(self, params: dict) -> str:
        account = params["account"]
        status = params.get("status", "all")

        if status == "all":
            status_filter = "t.status IN ('wait', 'doing')"
        else:
            status_filter = f"t.status = '{status}'"

        rows = self._db.fetch_all(
            f"""SELECT t.id, t.name, t.status, t.pri, t.estimate, t.consumed, t.`left`,
                       t.deadline, t.type, t.assignedTo,
                       p.name AS execution_name
                FROM zt_task t
                LEFT JOIN zt_project p ON t.execution = p.id
                WHERE t.assignedTo = %s AND t.deleted = '0' AND {status_filter}
                ORDER BY t.pri ASC, t.id DESC
                LIMIT 50""",
            (account,),
        )

        if not rows:
            return json.dumps({"ok": True, "count": 0, "tasks": [], "message": f"{account} 暂无待办任务"}, ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "count": len(rows),
            "tasks": rows,
        }, ensure_ascii=False, default=_json_serial)
