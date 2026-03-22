"""查询禅道任务详情"""

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


class TaskDetailTool(BaseTool):
    name = "zentao_task_detail"
    description = "查询禅道中某个任务的详细信息"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "任务 ID"},
            },
            "required": ["task_id"],
        }

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]

        row = self._db.fetch_one(
            """SELECT t.id, t.name, t.status, t.pri, t.type,
                      t.estimate, t.consumed, t.`left`, t.deadline,
                      t.assignedTo, t.openedBy, t.openedDate,
                      t.finishedBy, t.finishedDate, t.`desc`,
                      t.story, t.execution, t.project,
                      p.name AS execution_name,
                      pp.name AS project_name,
                      u.realname AS assigned_name
               FROM zt_task t
               LEFT JOIN zt_project p ON t.execution = p.id
               LEFT JOIN zt_project pp ON t.project = pp.id
               LEFT JOIN zt_user u ON t.assignedTo = u.account
               WHERE t.id = %s AND t.deleted = '0'""",
            (task_id,),
        )

        if not row:
            return json.dumps({"ok": False, "message": f"任务 #{task_id} 不存在"}, ensure_ascii=False)

        return json.dumps({"ok": True, "task": row}, ensure_ascii=False, default=_json_serial)
