"""创建禅道 Bug"""

import json
import asyncio

from openvort.plugin.base import BaseTool
from openvort.plugins.zentao.db import ZentaoDB, AI_ACCOUNT, get_actor, get_actor_display


class CreateBugTool(BaseTool):
    name = "zentao_create_bug"
    description = "在禅道中创建一个 Bug，需要指定产品、标题和复现步骤；可选挂载到项目/迭代"

    def __init__(self, db: ZentaoDB):
        self._db = db

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "产品名称或 code"},
                "title": {"type": "string", "description": "Bug 标题"},
                "steps": {"type": "string", "description": "复现步骤/详细说明"},
                "project": {"type": ["integer", "string"], "description": "所属项目 ID 或名称（可选）"},
                "execution": {"type": ["integer", "string"], "description": "所属迭代 ID 或名称（可选）"},
                "severity": {"type": "integer", "description": "严重程度 1-4（1最严重）", "default": 3},
                "pri": {"type": "integer", "description": "优先级 1-4", "default": 3},
                "assigned_to": {"type": "string", "description": "指派人账号（可选）", "default": ""},
                "bug_type": {"type": "string", "description": "Bug 类型", "default": "codeerror",
                             "enum": ["codeerror", "config", "install", "security", "performance",
                                      "standard", "automation", "designdefect", "others"]},
                "image_urls": {"type": "array", "items": {"type": "string"},
                               "description": "截图 URL 列表（用户发送的图片地址，从 _image_urls 获取）"},
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
        project_param = params.get("project")
        execution_param = params.get("execution")

        image_files = params.get("_image_files", []) or []
        image_urls = params.get("image_urls", []) or []
        injected_urls = params.get("_image_urls", []) or []
        for url in injected_urls:
            if url and url not in image_urls:
                image_urls.append(url)

        img_srcs = []
        for img in image_files:
            mt = img.get("media_type", "image/png")
            img_srcs.append(f"data:{mt};base64,{img['data']}")
        if not img_srcs:
            img_srcs = list(image_urls)

        if img_srcs:
            img_html = "\n".join(
                f'<img src="{src}" alt="截图" style="max-width:100%;" />'
                for src in img_srcs
            )
            steps = f"{steps}\n<p>截图：</p>\n{img_html}"

        # 查产品 ID
        product_id = self._db.find_product_id(product_name)
        if not product_id:
            return json.dumps({"ok": False, "message": f"未找到产品「{product_name}」"}, ensure_ascii=False)

        def _resolve_project_id(value) -> int:
            if value is None or value == "":
                return 0
            if isinstance(value, int):
                row = self._db.fetch_one(
                    "SELECT id FROM zt_project WHERE id=%s AND deleted='0' AND type='project' LIMIT 1",
                    (value,),
                )
                return row["id"] if row else 0
            return self._db.find_project_id(str(value)) or 0

        def _resolve_execution_id(value) -> int:
            if value is None or value == "":
                return 0
            if isinstance(value, int):
                row = self._db.fetch_one(
                    "SELECT id FROM zt_project WHERE id=%s AND deleted='0' AND type='sprint' LIMIT 1",
                    (value,),
                )
                return row["id"] if row else 0
            return self._db.find_execution_id(str(value)) or 0

        project_id = _resolve_project_id(project_param)
        execution_id = _resolve_execution_id(execution_param)

        if project_param not in (None, "") and not project_id:
            return json.dumps({"ok": False, "message": f"未找到项目「{project_param}」"}, ensure_ascii=False)
        if execution_param not in (None, "") and not execution_id:
            return json.dumps({"ok": False, "message": f"未找到迭代「{execution_param}」"}, ensure_ascii=False)

        # 传了迭代时，优先使用迭代归属项目，避免继续落到 project=0
        if execution_id:
            execution_project_id = self._db.get_execution_project(execution_id) or 0
            if execution_project_id:
                if project_id and project_id != execution_project_id:
                    return json.dumps(
                        {
                            "ok": False,
                            "message": f"项目/迭代不匹配：迭代 #{execution_id} 不属于项目 #{project_id}",
                        },
                        ensure_ascii=False,
                    )
                project_id = execution_project_id

        def _do_create():
            actor = get_actor(params)
            actor_display = get_actor_display(self._db, params)
            conn = self._db.get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO zt_bug
                           (product, project, execution, title, status,
                            severity, pri, type, steps,
                            openedBy, openedDate, assignedTo,
                            openedBuild, deleted)
                           VALUES (%s, %s, %s, %s, 'active',
                            %s, %s, %s, %s,
                            %s, NOW(), %s,
                            'trunk', '0')""",
                        (product_id, project_id, execution_id, title, severity, pri, bug_type, steps,
                         actor, assigned_to),
                    )
                    bug_id = cur.lastrowid
                    self._db.log_action(
                        cur, "bug", bug_id, "opened",
                        product=product_id, project=project_id, execution=execution_id, actor=actor,
                        comment=f"由 {actor_display} 通过 OpenVort 创建：{title}",
                    )
                conn.commit()
                return bug_id
            finally:
                conn.close()

        bug_id = await asyncio.to_thread(_do_create)

        return json.dumps({
            "ok": True,
            "bug_id": bug_id,
            "message": f"Bug #{bug_id}「{title}」已创建（project={project_id}, execution={execution_id}）",
        }, ensure_ascii=False)
