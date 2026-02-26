"""更新禅道任务（状态/指派/完成）"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT


class UpdateTaskTool(BaseTool):
    name = "zentao_update_task"
    description = "更新禅道任务：修改状态、指派给他人、标记完成等"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "任务 ID"},
                "action": {"type": "string", "description": "操作类型",
                           "enum": ["update_status", "assign", "finish"]},
                "status": {"type": "string", "description": "新状态（action=update_status 时必填）",
                           "enum": ["wait", "doing", "done", "cancel", "closed"]},
                "assigned_to": {"type": "string", "description": "指派人账号（action=assign 时必填）"},
                "consumed": {"type": "number", "description": "实际工时（action=finish 时可选）", "default": 0},
                "comment": {"type": "string", "description": "备注", "default": ""},
            },
            "required": ["task_id", "action"],
        }

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]
        action = params["action"]

        # 查任务基本信息
        task = self._db.fetch_one(
            "SELECT id, execution, status, assignedTo, consumed FROM zt_task WHERE id=%s AND deleted='0'",
            (task_id,),
        )
        if not task:
            return json.dumps({"ok": False, "message": f"任务 #{task_id} 不存在"}, ensure_ascii=False)

        execution = task["execution"]
        project = self._db.get_execution_project(execution) or 0

        def _do_update():
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    if action == "assign":
                        account = params.get("assigned_to", "")
                        if not account:
                            return {"ok": False, "message": "指派操作需要 assigned_to 参数"}
                        old_assignee = task.get("assignedTo", "")
                        cur.execute(
                            """UPDATE zt_task SET assignedTo=%s, assignedDate=NOW(),
                               lastEditedBy=%s, lastEditedDate=NOW() WHERE id=%s""",
                            (account, AI_ACCOUNT, task_id),
                        )
                        self._db.log_action(
                            cur, "task", task_id, "assigned",
                            project=project, execution=execution,
                            comment=f"由 {AI_ACCOUNT} 指派给 {account}（原：{old_assignee}）",
                            extra=account,
                        )
                        msg = f"任务 #{task_id} 已指派给 {account}"

                    elif action == "finish":
                        consumed = params.get("consumed", 0)
                        old_consumed = float(task.get("consumed", 0))
                        total = old_consumed + consumed if consumed else old_consumed
                        comment = params.get("comment", f"由 {AI_ACCOUNT} 标记完成")
                        cur.execute(
                            """UPDATE zt_task SET status='done', finishedBy=%s, finishedDate=NOW(),
                               consumed=%s, `left`=0, lastEditedBy=%s, lastEditedDate=NOW()
                               WHERE id=%s""",
                            (AI_ACCOUNT, total, AI_ACCOUNT, task_id),
                        )
                        self._db.log_action(
                            cur, "task", task_id, "finished",
                            project=project, execution=execution,
                            comment=comment,
                        )
                        msg = f"任务 #{task_id} 已完成"

                    elif action == "update_status":
                        status = params.get("status", "doing")
                        sets = ["status=%s", "lastEditedBy=%s", "lastEditedDate=NOW()"]
                        vals = [status, AI_ACCOUNT]
                        if status == "doing":
                            sets.append("realStarted=NOW()")
                        elif status == "done":
                            sets.extend(["finishedBy=%s", "finishedDate=NOW()", "`left`=0"])
                            vals.append(AI_ACCOUNT)
                        elif status == "cancel":
                            sets.extend(["canceledBy=%s", "canceledDate=NOW()"])
                            vals.append(AI_ACCOUNT)
                        elif status == "closed":
                            sets.extend(["closedBy=%s", "closedDate=NOW()", "closedReason='done'"])
                            vals.append(AI_ACCOUNT)
                        vals.append(task_id)
                        cur.execute(f"UPDATE zt_task SET {', '.join(sets)} WHERE id=%s", vals)
                        self._db.log_action(
                            cur, "task", task_id, "edited",
                            project=project, execution=execution,
                            comment=f"由 {AI_ACCOUNT} 更新状态为 {status}",
                        )
                        msg = f"任务 #{task_id} 状态已更新为 {status}"
                    else:
                        return {"ok": False, "message": f"未知操作: {action}"}

                conn.commit()
                return {"ok": True, "message": msg}
            finally:
                conn.close()

        result = await asyncio.to_thread(_do_update)
        return json.dumps(result, ensure_ascii=False)
