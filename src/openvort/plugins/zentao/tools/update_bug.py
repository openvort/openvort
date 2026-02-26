"""更新禅道 Bug（编辑内容/指派/关闭/追加图片等）"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor


class UpdateBugTool(BaseTool):
    name = "zentao_update_bug"
    description = "更新禅道 Bug：编辑标题/步骤、追加截图、修改严重程度、指派、确认、关闭等"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "bug_id": {"type": "integer", "description": "Bug ID"},
                "title": {"type": "string", "description": "新标题（可选，不传则不修改）"},
                "steps": {"type": "string", "description": "新的复现步骤（可选，完整替换）"},
                "append_steps": {"type": "string", "description": "追加到现有步骤末尾的内容（可选，与 steps 二选一）"},
                "severity": {"type": "integer", "description": "严重程度 1-4（可选）"},
                "pri": {"type": "integer", "description": "优先级 1-4（可选）"},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）"},
                "status": {"type": "string", "description": "状态变更（可选）",
                           "enum": ["active", "confirmed", "resolved", "closed"]},
                "resolution": {"type": "string", "description": "解决方案（status=resolved 时使用）",
                               "enum": ["bydesign", "duplicate", "external", "fixed",
                                        "notrepro", "postponed", "willnotfix", "tostory"],
                               "default": "fixed"},
                "image_urls": {"type": "array", "items": {"type": "string"},
                               "description": "截图 URL 列表，追加到 steps 末尾"},
            },
            "required": ["bug_id"],
        }

    async def execute(self, params: dict) -> str:
        bug_id = params["bug_id"]

        # 查 Bug
        bug = self._db.fetch_one(
            "SELECT id, product, title, steps, status, assignedTo FROM zt_bug WHERE id=%s AND deleted='0'",
            (bug_id,),
        )
        if not bug:
            return json.dumps({"ok": False, "message": f"Bug #{bug_id} 不存在"}, ensure_ascii=False)

        # 合并图片 URL
        image_urls = params.get("image_urls", []) or []
        injected_urls = params.get("_image_urls", []) or []
        for url in injected_urls:
            if url and url not in image_urls:
                image_urls.append(url)

        def _do_update():
            actor = get_actor(params)
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    sets, vals, changes = [], [], []

                    # 标题
                    if "title" in params and params["title"]:
                        sets.append("title=%s")
                        vals.append(params["title"])
                        changes.append(f"标题→{params['title']}")

                    # 步骤：完整替换 or 追加
                    new_steps = None
                    if "steps" in params and params["steps"]:
                        new_steps = params["steps"]
                        changes.append("步骤已更新")
                    elif "append_steps" in params and params["append_steps"]:
                        old_steps = bug.get("steps", "") or ""
                        new_steps = f"{old_steps}\n{params['append_steps']}"
                        changes.append("步骤已追加")

                    # 追加图片到 steps
                    if image_urls:
                        img_html = "\n".join(
                            f'<img src="{url}" alt="截图" style="max-width:100%;" />'
                            for url in image_urls
                        )
                        base = new_steps if new_steps else (bug.get("steps", "") or "")
                        new_steps = f"{base}\n<p>截图：</p>\n{img_html}"
                        changes.append(f"追加 {len(image_urls)} 张截图")

                    if new_steps is not None:
                        sets.append("steps=%s")
                        vals.append(new_steps)

                    # 严重程度 / 优先级
                    if "severity" in params:
                        sets.append("severity=%s")
                        vals.append(params["severity"])
                        changes.append(f"严重程度→{params['severity']}")
                    if "pri" in params:
                        sets.append("pri=%s")
                        vals.append(params["pri"])
                        changes.append(f"优先级→{params['pri']}")

                    # 指派
                    if "assigned_to" in params and params["assigned_to"]:
                        sets.append("assignedTo=%s")
                        vals.append(params["assigned_to"])
                        sets.append("assignedDate=NOW()")
                        changes.append(f"指派→{params['assigned_to']}")

                    # 状态变更
                    status = params.get("status")
                    if status:
                        sets.append("status=%s")
                        vals.append(status)
                        if status == "confirmed":
                            sets.extend(["confirmed=1"])
                            changes.append("已确认")
                        elif status == "resolved":
                            resolution = params.get("resolution", "fixed")
                            sets.extend(["resolution=%s", "resolvedBy=%s", "resolvedDate=NOW()"])
                            vals.extend([resolution, actor])
                            changes.append(f"已解决({resolution})")
                        elif status == "closed":
                            sets.extend(["closedBy=%s", "closedDate=NOW()"])
                            vals.append(actor)
                            changes.append("已关闭")
                        else:
                            changes.append(f"状态→{status}")

                    if not sets:
                        return {"ok": False, "message": "没有需要更新的字段"}

                    sets.extend(["lastEditedBy=%s", "lastEditedDate=NOW()"])
                    vals.append(actor)
                    vals.append(bug_id)

                    sql = f"UPDATE zt_bug SET {', '.join(sets)} WHERE id=%s"
                    cur.execute(sql, vals)

                    action_type = "edited"
                    if status == "resolved":
                        action_type = "resolved"
                    elif status == "closed":
                        action_type = "closed"

                    self._db.log_action(
                        cur, "bug", bug_id, action_type,
                        product=bug.get("product", 0), actor=actor,
                        comment=f"由 {actor} 通过 OpenVort 更新：{'、'.join(changes)}",
                    )
                conn.commit()
                return {"ok": True, "message": f"Bug #{bug_id} 已更新：{'、'.join(changes)}"}
            finally:
                conn.close()

        result = await asyncio.to_thread(_do_update)
        return json.dumps(result, ensure_ascii=False)
