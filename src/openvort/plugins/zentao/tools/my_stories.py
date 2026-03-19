"""查询个人需求列表"""

import json
from datetime import datetime, date

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB


def _json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


class MyStoriesTool(BaseTool):
    name = "zentao_my_stories"
    description = "查询指定人员在禅道中的需求列表"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "人员账号（禅道 UserID）"},
                "status": {"type": "string", "description": "筛选状态（可选）",
                           "enum": ["active", "closed", "all"], "default": "active"},
            },
            "required": ["account"],
        }

    async def execute(self, params: dict) -> str:
        account = params["account"]
        status = params.get("status", "active")

        where = "s.assignedTo = %s AND s.deleted = '0'"
        args = [account]
        if status and status != "all":
            where += " AND s.status = %s"
            args.append(status)

        rows = self._db.fetch_all(
            f"""SELECT s.id, s.title, s.status, s.pri, s.estimate, s.category,
                       s.openedBy, s.openedDate, s.assignedTo,
                       p.name AS product_name
                FROM zt_story s
                LEFT JOIN zt_product p ON s.product = p.id
                WHERE {where}
                ORDER BY s.pri ASC, s.id DESC
                LIMIT 50""",
            tuple(args),
        )

        if not rows:
            return json.dumps({"ok": True, "count": 0, "stories": [],
                               "message": f"{account} 暂无{'待处理' if status == 'active' else ''}需求"},
                              ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "count": len(rows),
            "stories": rows,
        }, ensure_ascii=False, default=_json_serial)
