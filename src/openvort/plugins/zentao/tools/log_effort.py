"""记录禅道任务工时"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor


class LogEffortTool(BaseTool):
    name = "zentao_log_effort"
    description = "为禅道任务记录工时（消耗时间和剩余时间）"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "任务 ID"},
                "account": {"type": "string", "description": "记录人账号"},
                "consumed": {"type": "number", "description": "本次消耗工时（小时）"},
                "left": {"type": "number", "description": "剩余工时（小时）", "default": 0},
                "work": {"type": "string", "description": "工作内容描述", "default": ""},
            },
            "required": ["task_id", "account", "consumed"],
        }

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]
        account = params["account"]
        consumed = params["consumed"]
        left = params.get("left", 0)
        work = params.get("work", "")

        # 查任务当前状态
        task = self._db.fetch_one(
            "SELECT id, execution, status, consumed, `left` FROM zt_task WHERE id=%s AND deleted='0'",
            (task_id,),
        )
        if not task:
            return json.dumps({"ok": False, "message": f"任务 #{task_id} 不存在"}, ensure_ascii=False)

        execution = task["execution"]
        project = self._db.get_execution_project(execution) or 0
        old_consumed = float(task.get("consumed", 0))
        total_consumed = old_consumed + consumed

        def _do_log():
            actor = get_actor(params)
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    # 插入 zt_effort
                    cur.execute(
                        """INSERT INTO zt_effort
                           (objectType, objectID, product, project, execution,
                            account, consumed, `left`, begin, end, work, date)
                           VALUES ('task', %s, 0, %s, %s,
                            %s, %s, %s, NOW(), NOW(), %s, CURDATE())""",
                        (task_id, project, execution,
                         account, consumed, left, work),
                    )

                    # 更新 zt_task 的 consumed 和 left
                    sets = ["consumed=%s", "`left`=%s", "lastEditedBy=%s", "lastEditedDate=NOW()"]
                    vals = [total_consumed, left, actor]

                    # 如果原状态是 wait，自动改为 doing
                    if task["status"] == "wait":
                        sets.extend(["status='doing'", "realStarted=NOW()"])

                    vals.append(task_id)
                    cur.execute(f"UPDATE zt_task SET {', '.join(sets)} WHERE id=%s", vals)

                    # 审计日志
                    self._db.log_action(
                        cur, "task", task_id, "recordEstimate",
                        project=project, execution=execution,
                        comment=f"{account} 记录工时 {consumed}h，剩余 {left}h。{work}",
                    )
                conn.commit()
                return {"ok": True, "message": f"任务 #{task_id} 已记录工时 {consumed}h，累计 {total_consumed}h"}
            finally:
                conn.close()

        result = await asyncio.to_thread(_do_log)
        return json.dumps(result, ensure_ascii=False)
