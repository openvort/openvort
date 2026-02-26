"""更新禅道需求（编辑内容/指派/关闭/追加图片等）"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor


class UpdateStoryTool(BaseTool):
    name = "zentao_update_story"
    description = "更新禅道需求：编辑标题/描述、追加截图、修改优先级、指派、关闭等"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer", "description": "需求 ID"},
                "title": {"type": "string", "description": "新标题（可选）"},
                "spec": {"type": "string", "description": "新描述（完整替换，可选）"},
                "append_spec": {"type": "string", "description": "追加到描述末尾（可选，与 spec 二选一）"},
                "pri": {"type": "integer", "description": "优先级 1-4（可选）"},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）"},
                "status": {"type": "string", "description": "状态变更（可选）",
                           "enum": ["active", "closed"]},
                "closed_reason": {"type": "string", "description": "关闭原因（status=closed 时）",
                                  "enum": ["done", "subdivided", "duplicate", "postponed",
                                           "willnotfix", "bydesign", "cancel"],
                                  "default": "done"},
                "image_urls": {"type": "array", "items": {"type": "string"},
                               "description": "截图 URL 列表，追加到描述末尾"},
            },
            "required": ["story_id"],
        }

    async def execute(self, params: dict) -> str:
        story_id = params["story_id"]

        story = self._db.fetch_one(
            "SELECT s.id, s.product, s.title, s.status, s.version, s.assignedTo, "
            "sp.spec FROM zt_story s "
            "LEFT JOIN zt_storyspec sp ON sp.story=s.id AND sp.version=s.version "
            "WHERE s.id=%s AND s.deleted='0'",
            (story_id,),
        )
        if not story:
            return json.dumps({"ok": False, "message": f"需求 #{story_id} 不存在"}, ensure_ascii=False)

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
                    update_spec = False
                    new_spec = None

                    if "title" in params and params["title"]:
                        sets.append("title=%s")
                        vals.append(params["title"])
                        changes.append(f"标题→{params['title']}")

                    # 描述：替换 or 追加
                    if "spec" in params and params["spec"]:
                        new_spec = params["spec"]
                        update_spec = True
                        changes.append("描述已更新")
                    elif "append_spec" in params and params["append_spec"]:
                        old_spec = story.get("spec", "") or ""
                        new_spec = f"{old_spec}\n{params['append_spec']}"
                        update_spec = True
                        changes.append("描述已追加")

                    if image_urls:
                        img_html = "\n".join(
                            f'<img src="{url}" alt="截图" style="max-width:100%;" />'
                            for url in image_urls
                        )
                        base = new_spec if new_spec else (story.get("spec", "") or "")
                        new_spec = f"{base}\n<p>截图：</p>\n{img_html}"
                        update_spec = True
                        changes.append(f"追加 {len(image_urls)} 张截图")

                    if "pri" in params:
                        sets.append("pri=%s")
                        vals.append(params["pri"])
                        changes.append(f"优先级→{params['pri']}")

                    if "assigned_to" in params and params["assigned_to"]:
                        sets.append("assignedTo=%s")
                        vals.append(params["assigned_to"])
                        sets.append("assignedDate=NOW()")
                        changes.append(f"指派→{params['assigned_to']}")

                    status = params.get("status")
                    if status:
                        sets.append("status=%s")
                        vals.append(status)
                        if status == "closed":
                            reason = params.get("closed_reason", "done")
                            sets.extend(["closedBy=%s", "closedDate=NOW()", "closedReason=%s"])
                            vals.extend([actor, reason])
                            changes.append(f"已关闭({reason})")
                        else:
                            changes.append(f"状态→{status}")

                    if not sets and not update_spec:
                        return {"ok": False, "message": "没有需要更新的字段"}

                    # 更新 zt_story
                    if sets:
                        sets.extend(["lastEditedBy=%s", "lastEditedDate=NOW()"])
                        vals.append(actor)
                        vals.append(story_id)
                        cur.execute(f"UPDATE zt_story SET {', '.join(sets)} WHERE id=%s", vals)

                    # 更新 zt_storyspec
                    if update_spec:
                        version = story.get("version", 1)
                        new_title = params.get("title") or story.get("title", "")
                        cur.execute(
                            "UPDATE zt_storyspec SET spec=%s, title=%s WHERE story=%s AND version=%s",
                            (new_spec, new_title, story_id, version),
                        )

                    action_type = "closed" if status == "closed" else "edited"
                    self._db.log_action(
                        cur, "story", story_id, action_type,
                        product=story.get("product", 0), actor=actor,
                        comment=f"由 {actor} 通过 OpenVort 更新：{'、'.join(changes)}",
                    )
                conn.commit()
                return {"ok": True, "message": f"需求 #{story_id} 已更新：{'、'.join(changes)}"}
            finally:
                conn.close()

        result = await asyncio.to_thread(_do_update)
        return json.dumps(result, ensure_ascii=False)
