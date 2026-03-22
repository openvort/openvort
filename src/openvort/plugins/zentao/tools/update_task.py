"""更新禅道任务（状态/指派/编辑内容/追加图片）"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor, get_actor_display


class UpdateTaskTool(BaseTool):
    name = "zentao_update_task"
    description = "更新禅道任务：修改状态、指派、编辑名称/描述、追加截图等"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "任务 ID"},
                "action": {"type": "string", "description": "操作类型（可选，不传则按字段自动判断）",
                           "enum": ["update_status", "assign", "finish"]},
                "name": {"type": "string", "description": "新任务名称（可选）"},
                "desc": {"type": "string", "description": "新描述（完整替换，可选）"},
                "append_desc": {"type": "string", "description": "追加到描述末尾（可选，与 desc 二选一）"},
                "status": {"type": "string", "description": "新状态（可选）",
                           "enum": ["wait", "doing", "done", "cancel", "closed"]},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）"},
                "pri": {"type": "integer", "description": "优先级 1-4（可选）"},
                "consumed": {"type": "number", "description": "实际工时（action=finish 时可选）", "default": 0},
                "comment": {"type": "string", "description": "备注", "default": ""},
                "image_urls": {"type": "array", "items": {"type": "string"},
                               "description": "截图 URL 列表，追加到描述末尾"},
            },
            "required": ["task_id"],
        }

    async def execute(self, params: dict) -> str:
        task_id = params["task_id"]
        action = params.get("action")

        task = self._db.fetch_one(
            "SELECT id, execution, status, assignedTo, consumed, `desc` FROM zt_task WHERE id=%s AND deleted='0'",
            (task_id,),
        )
        if not task:
            return json.dumps({"ok": False, "message": f"任务 #{task_id} 不存在"}, ensure_ascii=False)

        execution = task["execution"]
        project = self._db.get_execution_project(execution) or 0

        # 合并图片 URL
        image_urls = params.get("image_urls", []) or []
        injected_urls = params.get("_image_urls", []) or []
        for url in injected_urls:
            if url and url not in image_urls:
                image_urls.append(url)

        def _do_update():
            actor = get_actor(params)
            actor_display = get_actor_display(self._db, params)
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    # 有明确 action 走原有逻辑
                    if action == "assign":
                        account = params.get("assigned_to", "")
                        if not account:
                            return {"ok": False, "message": "指派操作需要 assigned_to 参数"}
                        old_assignee = task.get("assignedTo", "")
                        cur.execute(
                            """UPDATE zt_task SET assignedTo=%s, assignedDate=NOW(),
                               lastEditedBy=%s, lastEditedDate=NOW() WHERE id=%s""",
                            (account, actor, task_id),
                        )
                        self._db.log_action(
                            cur, "task", task_id, "assigned",
                            project=project, execution=execution, actor=actor,
                            comment=f"由 {actor_display} 指派给 {account}（原：{old_assignee}）",
                            extra=account,
                        )
                        conn.commit()
                        return {"ok": True, "message": f"任务 #{task_id} 已指派给 {account}"}

                    if action == "finish":
                        consumed = params.get("consumed", 0)
                        old_consumed = float(task.get("consumed", 0))
                        total = old_consumed + consumed if consumed else old_consumed
                        comment = params.get("comment", f"由 {actor_display} 标记完成")
                        cur.execute(
                            """UPDATE zt_task SET status='done', finishedBy=%s, finishedDate=NOW(),
                               consumed=%s, `left`=0, lastEditedBy=%s, lastEditedDate=NOW()
                               WHERE id=%s""",
                            (actor, total, actor, task_id),
                        )
                        self._db.log_action(
                            cur, "task", task_id, "finished",
                            project=project, execution=execution, actor=actor,
                            comment=comment,
                        )
                        conn.commit()
                        return {"ok": True, "message": f"任务 #{task_id} 已完成"}

                    # 通用编辑模式
                    sets, vals, changes = [], [], []

                    if "name" in params and params["name"]:
                        sets.append("name=%s")
                        vals.append(params["name"])
                        changes.append(f"名称→{params['name']}")

                    # 描述：替换 or 追加
                    new_desc = None
                    if "desc" in params and params["desc"]:
                        new_desc = params["desc"]
                        changes.append("描述已更新")
                    elif "append_desc" in params and params["append_desc"]:
                        old_desc = task.get("desc", "") or ""
                        new_desc = f"{old_desc}\n{params['append_desc']}"
                        changes.append("描述已追加")

                    if image_urls:
                        img_html = "\n".join(
                            f'<img src="{url}" alt="截图" style="max-width:100%;" />'
                            for url in image_urls
                        )
                        base = new_desc if new_desc else (task.get("desc", "") or "")
                        new_desc = f"{base}\n<p>截图：</p>\n{img_html}"
                        changes.append(f"追加 {len(image_urls)} 张截图")

                    if new_desc is not None:
                        sets.append("`desc`=%s")
                        vals.append(new_desc)

                    if "pri" in params:
                        sets.append("pri=%s")
                        vals.append(params["pri"])
                        changes.append(f"优先级→{params['pri']}")

                    if "assigned_to" in params and params["assigned_to"]:
                        sets.append("assignedTo=%s")
                        vals.append(params["assigned_to"])
                        sets.append("assignedDate=NOW()")
                        changes.append(f"指派→{params['assigned_to']}")

                    if action == "update_status" or ("status" in params and params.get("status")):
                        status = params.get("status", "doing")
                        sets.append("status=%s")
                        vals.append(status)
                        if status == "doing":
                            sets.append("realStarted=NOW()")
                        elif status == "done":
                            sets.extend(["finishedBy=%s", "finishedDate=NOW()", "`left`=0"])
                            vals.append(actor)
                        elif status == "cancel":
                            sets.extend(["canceledBy=%s", "canceledDate=NOW()"])
                            vals.append(actor)
                        elif status == "closed":
                            sets.extend(["closedBy=%s", "closedDate=NOW()", "closedReason='done'"])
                            vals.append(actor)
                        changes.append(f"状态→{status}")

                    if not sets:
                        return {"ok": False, "message": "没有需要更新的字段"}

                    sets.extend(["lastEditedBy=%s", "lastEditedDate=NOW()"])
                    vals.append(actor)
                    vals.append(task_id)

                    cur.execute(f"UPDATE zt_task SET {', '.join(sets)} WHERE id=%s", vals)
                    self._db.log_action(
                        cur, "task", task_id, "edited",
                        project=project, execution=execution, actor=actor,
                        comment=f"由 {actor_display} 通过 OpenVort 更新：{'、'.join(changes)}",
                    )
                conn.commit()
                return {"ok": True, "message": f"任务 #{task_id} 已更新：{'、'.join(changes)}"}
            finally:
                conn.close()

        result = await asyncio.to_thread(_do_update)
        return json.dumps(result, ensure_ascii=False)
