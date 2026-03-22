"""查询个人待办 Bug"""

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


class MyBugsTool(BaseTool):
    name = "zentao_my_bugs"
    description = "查询指定人员在禅道中的待解决 Bug 列表"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "account": {"type": "string", "description": "人员账号（禅道 UserID）"},
            },
            "required": ["account"],
        }

    async def execute(self, params: dict) -> str:
        account = params["account"]

        rows = self._db.fetch_all(
            """SELECT b.id, b.title, b.status, b.severity, b.pri, b.type,
                      b.openedBy, b.openedDate, b.assignedTo,
                      p.name AS product_name
               FROM zt_bug b
               LEFT JOIN zt_product p ON b.product = p.id
               WHERE b.assignedTo = %s AND b.deleted = '0' AND b.status = 'active'
               ORDER BY b.severity ASC, b.pri ASC, b.id DESC
               LIMIT 50""",
            (account,),
        )

        if not rows:
            return json.dumps({"ok": True, "count": 0, "bugs": [], "message": f"{account} 暂无待解决 Bug"}, ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "count": len(rows),
            "bugs": rows,
        }, ensure_ascii=False, default=_json_serial)
