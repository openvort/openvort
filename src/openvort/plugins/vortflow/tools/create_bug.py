"""
创建缺陷工具 -- vortflow_create_bug
"""

import json

from sqlalchemy import select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.create_bug")


class CreateBugTool(BaseTool):
    name = "vortflow_create_bug"
    description = (
        "在 VortFlow 中提交新缺陷(Bug)。"
        "可关联到需求或任务，指定严重程度和负责人。"
        "支持通过迭代名称或 ID 关联迭代。"
        "创建后缺陷进入 open 状态。"
    )
    required_permission = "vortflow.bug"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "缺陷标题"},
                "description": {"type": "string", "description": "缺陷描述（重现步骤、期望结果等）", "default": ""},
                "project_id": {
                    "type": "string",
                    "description": "所属项目 ID（如提供 story_id/task_id 可自动继承）",
                    "default": "",
                },
                "story_id": {
                    "type": "string",
                    "description": "关联需求 ID（可选）",
                    "default": "",
                },
                "task_id": {
                    "type": "string",
                    "description": "关联任务 ID（可选）",
                    "default": "",
                },
                "severity": {
                    "type": "integer",
                    "description": "严重程度: 1=致命 2=严重 3=一般 4=轻微",
                    "default": 3,
                    "enum": [1, 2, 3, 4],
                },
                "assignee_name": {
                    "type": "string",
                    "description": "负责修复人的姓名",
                    "default": "",
                },
                "iteration_id": {
                    "type": "string",
                    "description": "关联迭代 ID（可选，与 iteration_name 二选一）",
                    "default": "",
                },
                "iteration_name": {
                    "type": "string",
                    "description": "关联迭代名称（可选，按名称模糊匹配，优先精确匹配）",
                    "default": "",
                },
                "image_urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "截图 URL 列表（用户发送的图片地址，从 _image_urls 获取）",
                },
            },
            "required": ["title"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import (
            FlowBug, FlowEvent, FlowIteration, FlowIterationBug,
            FlowStory, FlowTask,
        )

        title = params["title"]
        description = params.get("description", "")

        image_urls = params.get("image_urls", []) or []
        injected_urls = params.get("_image_urls", []) or []
        for url in injected_urls:
            if url and url not in image_urls:
                image_urls.append(url)
        if image_urls:
            img_md = "\n".join(f"![截图]({url})" for url in image_urls)
            description = f"{description}\n\n{img_md}" if description else img_md

        project_id = params.get("project_id", "") or None
        story_id = params.get("story_id", "") or None
        task_id = params.get("task_id", "") or None
        severity = params.get("severity", 3)
        assignee_name = params.get("assignee_name", "")
        iteration_id = params.get("iteration_id", "") or None
        iteration_name = params.get("iteration_name", "") or None
        member_id = params.get("_member_id", "")

        sf = self._get_sf()
        async with sf() as session:
            if story_id:
                story = await session.get(FlowStory, story_id)
                if story and not project_id:
                    project_id = story.project_id
            if task_id and not project_id:
                task = await session.get(FlowTask, task_id)
                if task and task.project_id:
                    project_id = task.project_id

            assignee_id = None
            if assignee_name:
                result = await session.execute(
                    select(Member).where(Member.name == assignee_name)
                )
                m = result.scalar_one_or_none()
                if m:
                    assignee_id = m.id

            resolved_iteration = None
            if iteration_id:
                resolved_iteration = await session.get(FlowIteration, iteration_id)
                if not resolved_iteration:
                    return json.dumps({"ok": False, "message": f"迭代不存在: {iteration_id}"}, ensure_ascii=False)
            elif iteration_name:
                stmt = select(FlowIteration).where(FlowIteration.name == iteration_name)
                if project_id:
                    stmt = stmt.where(FlowIteration.project_id == project_id)
                result = await session.execute(stmt)
                resolved_iteration = result.scalar_one_or_none()
                if not resolved_iteration:
                    like = f"%{iteration_name}%"
                    stmt2 = select(FlowIteration).where(FlowIteration.name.ilike(like))
                    if project_id:
                        stmt2 = stmt2.where(FlowIteration.project_id == project_id)
                    result2 = await session.execute(stmt2.limit(5))
                    candidates = result2.scalars().all()
                    if len(candidates) == 1:
                        resolved_iteration = candidates[0]
                    elif len(candidates) > 1:
                        names = "、".join(f"「{c.name}」(ID:{c.id})" for c in candidates)
                        return json.dumps({
                            "ok": False,
                            "message": f"找到多个匹配迭代: {names}，请提供更精确的名称或直接使用 iteration_id",
                        }, ensure_ascii=False)
                    else:
                        return json.dumps({
                            "ok": False,
                            "message": f"未找到迭代「{iteration_name}」，请先通过 vortflow_query(query_type=iterations) 查询可用迭代",
                        }, ensure_ascii=False)

            b = FlowBug(
                project_id=project_id,
                story_id=story_id,
                task_id=task_id,
                title=title,
                description=description,
                severity=severity,
                assignee_id=assignee_id,
                reporter_id=member_id or None,
            )
            session.add(b)
            await session.flush()

            if resolved_iteration:
                link = FlowIterationBug(iteration_id=resolved_iteration.id, bug_id=b.id)
                session.add(link)

            event = FlowEvent(
                entity_type="bug",
                entity_id=b.id,
                action="created",
                actor_id=member_id or None,
                detail=json.dumps({"title": title}, ensure_ascii=False),
            )
            session.add(event)
            await session.commit()
            await session.refresh(b)
            bug_id = b.id

        severity_labels = {1: "致命", 2: "严重", 3: "一般", 4: "轻微"}
        result_data = {
            "ok": True,
            "message": f"缺陷「{title}」已提交，严重程度: {severity_labels.get(severity, '未知')}",
            "bug_id": bug_id,
            "project_id": project_id,
        }
        if resolved_iteration:
            result_data["iteration_id"] = resolved_iteration.id
            result_data["iteration_name"] = resolved_iteration.name
            result_data["message"] += f"，已关联迭代「{resolved_iteration.name}」"
        return json.dumps(result_data, ensure_ascii=False)
