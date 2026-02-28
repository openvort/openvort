"""创建禅道需求"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor, get_actor_display


class CreateStoryTool(BaseTool):
    name = "zentao_create_story"
    description = "在禅道中创建一个需求，需要指定产品、标题和描述"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "产品名称或 code"},
                "title": {"type": "string", "description": "需求标题"},
                "spec": {"type": "string", "description": "需求描述/详细说明"},
                "pri": {"type": "integer", "description": "优先级 1-4", "default": 3},
                "estimate": {"type": "number", "description": "预计工时（小时）", "default": 0},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）", "default": ""},
                "category": {"type": "string", "description": "需求类型", "default": "feature",
                             "enum": ["feature", "interface", "performance", "safe", "experience",
                                      "improve", "other"]},
                "image_urls": {"type": "array", "items": {"type": "string"},
                               "description": "截图 URL 列表，嵌入需求描述"},
            },
            "required": ["product", "title", "spec"],
        }

    async def execute(self, params: dict) -> str:
        product_name = params["product"]
        title = params["title"]
        spec = params["spec"]
        pri = params.get("pri", 3)
        estimate = params.get("estimate", 0)
        assigned_to = params.get("assigned_to", "")
        category = params.get("category", "feature")

        # 合并图片 URL
        image_urls = params.get("image_urls", []) or []
        injected_urls = params.get("_image_urls", []) or []
        for url in injected_urls:
            if url and url not in image_urls:
                image_urls.append(url)

        if image_urls:
            img_html = "\n".join(
                f'<img src="{url}" alt="截图" style="max-width:100%;" />'
                for url in image_urls
            )
            spec = f"{spec}\n<p>截图：</p>\n{img_html}"

        product_id = self._db.find_product_id(product_name)
        if not product_id:
            return json.dumps({"ok": False, "message": f"未找到产品「{product_name}」"}, ensure_ascii=False)

        def _do_create():
            actor = get_actor(params)
            actor_display = get_actor_display(self._db, params)
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    # 插入 zt_story
                    cur.execute(
                        """INSERT INTO zt_story
                           (product, title, status, pri, estimate,
                            category, assignedTo, assignedDate,
                            openedBy, openedDate, version, deleted)
                           VALUES (%s, %s, 'active', %s, %s,
                            %s, %s, NOW(),
                            %s, NOW(), 1, '0')""",
                        (product_id, title, pri, estimate,
                         category, assigned_to, actor),
                    )
                    story_id = cur.lastrowid

                    # 插入 zt_storyspec（需求描述存这里）
                    cur.execute(
                        """INSERT INTO zt_storyspec
                           (story, version, title, spec)
                           VALUES (%s, 1, %s, %s)""",
                        (story_id, title, spec),
                    )

                    self._db.log_action(
                        cur, "story", story_id, "opened",
                        product=product_id, actor=actor,
                        comment=f"由 {actor_display} 通过 OpenVort 创建：{title}",
                    )
                conn.commit()
                return story_id
            finally:
                conn.close()

        story_id = await asyncio.to_thread(_do_create)

        return json.dumps({
            "ok": True,
            "story_id": story_id,
            "message": f"需求 #{story_id}「{title}」已创建",
        }, ensure_ascii=False)
