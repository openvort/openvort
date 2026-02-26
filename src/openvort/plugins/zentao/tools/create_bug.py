"""创建禅道 Bug"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT


class CreateBugTool(BaseTool):
    name = "zentao_create_bug"
    description = "在禅道中创建一个 Bug，需要指定产品、标题和复现步骤"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "产品名称或 code"},
                "title": {"type": "string", "description": "Bug 标题"},
                "steps": {"type": "string", "description": "复现步骤/详细说明"},
                "severity": {"type": "integer", "description": "严重程度 1-4（1最严重）", "default": 3},
                "pri": {"type": "integer", "description": "优先级 1-4", "default": 3},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）", "default": ""},
                "bug_type": {"type": "string", "description": "Bug 类型", "default": "codeerror",
                             "enum": ["codeerror", "config", "install", "security", "performance",
                                      "standard", "automation", "designdefect", "others"]},
            },
            "required": ["product", "title", "steps"],
        }

    async def execute(self, params: dict) -> str:
        product_name = params["product"]
        title = params["title"]
        steps = params["steps"]
        severity = params.get("severity", 3)
        pri = params.get("pri", 3)
        assigned_to = params.get("assigned_to", "")
        bug_type = params.get("bug_type", "codeerror")

        # 查产品 ID
        product_id = self._db.find_product_id(product_name)
        if not product_id:
            return json.dumps({"ok": False, "message": f"未找到产品「{product_name}」"}, ensure_ascii=False)

        def _do_create():
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO zt_bug
                           (product, project, execution, title, status,
                            severity, pri, type, steps,
                            openedBy, openedDate, assignedTo,
                            openedBuild, deleted)
                           VALUES (%s, 0, 0, %s, 'active',
                            %s, %s, %s, %s,
                            %s, NOW(), %s,
                            'trunk', '0')""",
                        (product_id, title, severity, pri, bug_type, steps,
                         AI_ACCOUNT, assigned_to),
                    )
                    bug_id = cur.lastrowid
                    self._db.log_action(
                        cur, "bug", bug_id, "opened",
                        product=product_id,
                        comment=f"由 {AI_ACCOUNT} 通过 OpenVort 创建：{title}",
                    )
                conn.commit()
                return bug_id
            finally:
                conn.close()

        bug_id = await asyncio.to_thread(_do_create)

        return json.dumps({
            "ok": True,
            "bug_id": bug_id,
            "message": f"Bug #{bug_id}「{title}」已创建",
        }, ensure_ascii=False)
