"""创建禅道任务"""

import json

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor


class CreateTaskTool(BaseTool):
    name = "zentao_create_task"
    description = "在禅道中创建一个新任务，需要指定任务名称和所属迭代"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "任务名称"},
                "execution": {"type": "integer", "description": "所属迭代/执行 ID"},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）", "default": ""},
                "task_type": {"type": "string", "description": "任务类型", "default": "devel",
                              "enum": ["devel", "test", "design", "discuss", "ui", "affair", "misc"]},
                "pri": {"type": "integer", "description": "优先级 1-4", "default": 3},
                "estimate": {"type": "number", "description": "预计工时（小时）", "default": 0},
                "desc": {"type": "string", "description": "任务描述（可选）", "default": ""},
                "story": {"type": "integer", "description": "关联需求 ID（可选）", "default": 0},
            },
            "required": ["name", "execution"],
        }

    async def execute(self, params: dict) -> str:
        name = params["name"]
        execution = params["execution"]
        assigned_to = params.get("assigned_to", "")
        task_type = params.get("task_type", "devel")
        pri = params.get("pri", 3)
        estimate = params.get("estimate", 0)
        desc = params.get("desc", "")
        story = params.get("story", 0)

        # 查迭代所属项目
        project = self._db.get_execution_project(execution) or 0

        # 查需求关联产品
        product = 0
        if story:
            row = self._db.fetch_one("SELECT product FROM zt_story WHERE id=%s", (story,))
            if row:
                product = row["product"]

        def _do_create():
            import pymysql
            actor = get_actor(params)
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO zt_task
                           (name, execution, project, type, status, pri, estimate, `left`,
                            consumed, deadline, `desc`, story, parent, assignedTo, assignedDate,
                            openedBy, openedDate, deleted)
                           VALUES (%s, %s, %s, %s, 'wait', %s, %s, %s,
                            0, '', %s, %s, 0, %s, NOW(),
                            %s, NOW(), '0')""",
                        (name, execution, project, task_type, pri, estimate, estimate,
                         desc, story, assigned_to, actor),
                    )
                    task_id = cur.lastrowid
                    self._db.log_action(
                        cur, "task", task_id, "opened",
                        product=product, project=project, execution=execution, actor=actor,
                        comment=f"由 {actor} 创建任务：{name}",
                    )
                conn.commit()
                return task_id
            finally:
                conn.close()

        import asyncio
        task_id = await asyncio.to_thread(_do_create)

        return json.dumps({
            "ok": True,
            "task_id": task_id,
            "message": f"任务 #{task_id}「{name}」已创建",
        }, ensure_ascii=False)
