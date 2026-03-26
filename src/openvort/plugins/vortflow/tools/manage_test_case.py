"""
测试用例管理工具 -- vortflow_manage_test_case

管理测试模块（树形分类）、测试用例 CRUD、用例与工作项关联。
"""

import json

from sqlalchemy import delete as sa_delete, func, select

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortflow.tools.manage_test_case")


class ManageTestCaseTool(BaseTool):
    name = "vortflow_manage_test_case"
    description = (
        "管理 VortFlow 测试用例和测试模块。"
        "action=create_module 创建测试模块（分类），需提供 project_id 和 name。"
        "action=update_module 修改模块名称或父级。"
        "action=delete_module 删除模块（需先删除子模块）。"
        "action=list_modules 列出项目的测试模块树。"
        "action=create_case 创建测试用例，需提供 project_id 和 title。"
        "action=update_case 修改用例信息。"
        "action=delete_case 删除用例。"
        "action=list_cases 查询用例列表，可按模块/类型/优先级/关键词过滤。"
        "action=detail_case 获取用例详情。"
        "action=link_work_item 关联用例与工作项（需求/任务/缺陷）。"
        "action=unlink_work_item 取消关联。"
        "action=list_links 查询用例的关联工作项。"
    )
    required_permission = "vortflow.story"

    def __init__(self, get_session_factory):
        self._get_sf = get_session_factory

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "create_module", "update_module", "delete_module", "list_modules",
                        "create_case", "update_case", "delete_case", "list_cases", "detail_case",
                        "link_work_item", "unlink_work_item", "list_links",
                    ],
                    "description": "操作类型",
                },
                "project_id": {"type": "string", "description": "项目 ID"},
                "module_id": {"type": "string", "description": "模块 ID"},
                "parent_id": {"type": "string", "description": "父模块 ID（创建/移动模块时可选）"},
                "name": {"type": "string", "description": "模块名称"},
                "case_id": {"type": "string", "description": "用例 ID"},
                "title": {"type": "string", "description": "用例标题"},
                "precondition": {"type": "string", "description": "前置条件", "default": ""},
                "notes": {"type": "string", "description": "备注", "default": ""},
                "case_type": {
                    "type": "string", "enum": ["functional", "performance", "api", "ui", "security"],
                    "description": "用例类型",
                },
                "priority": {"type": "integer", "enum": [0, 1, 2, 3], "description": "优先级 (0=P0..3=P3)"},
                "maintainer_name": {"type": "string", "description": "维护人姓名", "default": ""},
                "review_result": {"type": "string", "enum": ["pending", "passed", "rejected"], "description": "评审结果"},
                "steps": {
                    "type": "array",
                    "items": {"type": "object", "properties": {
                        "order": {"type": "integer"}, "description": {"type": "string"},
                        "expected_result": {"type": "string"},
                    }},
                    "description": "测试步骤列表",
                },
                "entity_type": {"type": "string", "enum": ["story", "task", "bug"], "description": "工作项类型"},
                "entity_id": {"type": "string", "description": "工作项 ID"},
                "link_id": {"type": "string", "description": "关联 ID（取消关联时使用）"},
                "keyword": {"type": "string", "description": "搜索关键词", "default": ""},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        from openvort.contacts.models import Member
        from openvort.plugins.vortflow.models import FlowTestCase, FlowTestCaseWorkItem, FlowTestModule

        action = params["action"]
        member_id = params.get("_member_id", "")
        sf = self._get_sf()

        # ---- Module actions ----

        if action == "create_module":
            project_id = params.get("project_id", "")
            name = params.get("name", "")
            if not project_id or not name:
                return json.dumps({"ok": False, "message": "create_module 需要 project_id 和 name"})
            parent_id = params.get("parent_id") or None
            async with sf() as session:
                max_order = (await session.execute(
                    select(func.coalesce(func.max(FlowTestModule.sort_order), 0))
                    .where(FlowTestModule.project_id == project_id, FlowTestModule.parent_id == parent_id)
                )).scalar_one()
                mod = FlowTestModule(project_id=project_id, parent_id=parent_id, name=name, sort_order=max_order + 1)
                session.add(mod)
                await session.commit()
                await session.refresh(mod)
            return json.dumps({"ok": True, "message": f"模块「{name}」已创建", "module_id": mod.id}, ensure_ascii=False)

        elif action == "update_module":
            module_id = params.get("module_id", "")
            if not module_id:
                return json.dumps({"ok": False, "message": "update_module 需要 module_id"})
            async with sf() as session:
                mod = await session.get(FlowTestModule, module_id)
                if not mod:
                    return json.dumps({"ok": False, "message": "模块不存在"})
                changes = {}
                if "name" in params and params["name"]:
                    mod.name = params["name"]; changes["name"] = params["name"]
                if "parent_id" in params:
                    mod.parent_id = params["parent_id"] or None; changes["parent_id"] = params["parent_id"]
                if not changes:
                    return json.dumps({"ok": False, "message": "未提供任何修改字段"})
                await session.commit()
            return json.dumps({"ok": True, "message": f"模块「{mod.name}」已更新"}, ensure_ascii=False)

        elif action == "delete_module":
            module_id = params.get("module_id", "")
            if not module_id:
                return json.dumps({"ok": False, "message": "delete_module 需要 module_id"})
            async with sf() as session:
                mod = await session.get(FlowTestModule, module_id)
                if not mod:
                    return json.dumps({"ok": False, "message": "模块不存在"})
                children = (await session.execute(
                    select(FlowTestModule).where(FlowTestModule.parent_id == module_id))).scalars().first()
                if children:
                    return json.dumps({"ok": False, "message": "请先删除子模块"})
                name = mod.name
                for tc in (await session.execute(
                        select(FlowTestCase).where(FlowTestCase.module_id == module_id))).scalars().all():
                    tc.module_id = None
                await session.delete(mod)
                await session.commit()
            return json.dumps({"ok": True, "message": f"模块「{name}」已删除"}, ensure_ascii=False)

        elif action == "list_modules":
            project_id = params.get("project_id", "")
            if not project_id:
                return json.dumps({"ok": False, "message": "list_modules 需要 project_id"})
            async with sf() as session:
                rows = (await session.execute(
                    select(FlowTestModule).where(FlowTestModule.project_id == project_id)
                    .order_by(FlowTestModule.sort_order, FlowTestModule.created_at))).scalars().all()
                module_ids = [m.id for m in rows]
                counts: dict[str, int] = {}
                if module_ids:
                    counts = dict((await session.execute(
                        select(FlowTestCase.module_id, func.count())
                        .where(FlowTestCase.module_id.in_(module_ids))
                        .group_by(FlowTestCase.module_id))).all())
                items = [{"id": m.id, "name": m.name, "parent_id": m.parent_id,
                          "sort_order": m.sort_order, "case_count": counts.get(m.id, 0)} for m in rows]
            return json.dumps({"ok": True, "count": len(items), "modules": items}, ensure_ascii=False)

        # ---- Case actions ----

        elif action == "create_case":
            project_id = params.get("project_id", "")
            title = params.get("title", "")
            if not project_id or not title:
                return json.dumps({"ok": False, "message": "create_case 需要 project_id 和 title"})
            maintainer_id = None
            if params.get("maintainer_name"):
                async with sf() as session:
                    m = (await session.execute(select(Member).where(Member.name == params["maintainer_name"]))).scalar_one_or_none()
                    if m: maintainer_id = m.id
            steps = params.get("steps", [])
            async with sf() as session:
                tc = FlowTestCase(
                    project_id=project_id, module_id=params.get("module_id") or None,
                    title=title, precondition=params.get("precondition", ""), notes=params.get("notes", ""),
                    case_type=params.get("case_type", "functional"), priority=params.get("priority", 2),
                    maintainer_id=maintainer_id or (member_id or None),
                    steps_json=json.dumps(steps, ensure_ascii=False),
                )
                session.add(tc)
                await session.commit()
                await session.refresh(tc)
            return json.dumps({"ok": True, "message": f"用例「{title}」已创建", "case_id": tc.id}, ensure_ascii=False)

        elif action == "update_case":
            case_id = params.get("case_id", "")
            if not case_id:
                return json.dumps({"ok": False, "message": "update_case 需要 case_id"})
            async with sf() as session:
                tc = await session.get(FlowTestCase, case_id)
                if not tc:
                    return json.dumps({"ok": False, "message": "用例不存在"})
                changes = {}
                for field in ("title", "precondition", "notes", "case_type", "review_result"):
                    if field in params and params[field] is not None:
                        setattr(tc, field, params[field]); changes[field] = params[field]
                if "priority" in params and params["priority"] is not None:
                    tc.priority = params["priority"]; changes["priority"] = params["priority"]
                if "module_id" in params:
                    tc.module_id = params["module_id"] or None; changes["module_id"] = params["module_id"]
                if params.get("maintainer_name"):
                    m = (await session.execute(select(Member).where(Member.name == params["maintainer_name"]))).scalar_one_or_none()
                    if m: tc.maintainer_id = m.id; changes["maintainer"] = params["maintainer_name"]
                if "steps" in params and params["steps"] is not None:
                    tc.steps_json = json.dumps(params["steps"], ensure_ascii=False)
                    changes["steps"] = f"{len(params['steps'])} steps"
                if not changes:
                    return json.dumps({"ok": False, "message": "未提供任何修改字段"})
                await session.commit()
            return json.dumps({"ok": True, "message": f"用例「{tc.title}」已更新，修改字段: {'、'.join(changes.keys())}"}, ensure_ascii=False)

        elif action == "delete_case":
            case_id = params.get("case_id", "")
            if not case_id:
                return json.dumps({"ok": False, "message": "delete_case 需要 case_id"})
            async with sf() as session:
                tc = await session.get(FlowTestCase, case_id)
                if not tc:
                    return json.dumps({"ok": False, "message": "用例不存在"})
                title = tc.title
                await session.execute(sa_delete(FlowTestCaseWorkItem).where(FlowTestCaseWorkItem.test_case_id == case_id))
                await session.delete(tc)
                await session.commit()
            return json.dumps({"ok": True, "message": f"用例「{title}」已删除"}, ensure_ascii=False)

        elif action == "list_cases":
            project_id = params.get("project_id", "")
            if not project_id:
                return json.dumps({"ok": False, "message": "list_cases 需要 project_id"})
            async with sf() as session:
                stmt = select(FlowTestCase).where(FlowTestCase.project_id == project_id).order_by(FlowTestCase.created_at.desc()).limit(50)
                if params.get("module_id"): stmt = stmt.where(FlowTestCase.module_id == params["module_id"])
                if params.get("case_type"): stmt = stmt.where(FlowTestCase.case_type == params["case_type"])
                if params.get("priority") is not None: stmt = stmt.where(FlowTestCase.priority == params["priority"])
                if params.get("keyword"): stmt = stmt.where(FlowTestCase.title.ilike(f"%{params['keyword']}%"))
                rows = (await session.execute(stmt)).scalars().all()
                member_ids = list({tc.maintainer_id for tc in rows if tc.maintainer_id})
                member_map: dict[str, str] = {}
                if member_ids:
                    members = (await session.execute(select(Member).where(Member.id.in_(member_ids)))).scalars().all()
                    member_map = {m.id: m.name for m in members}
                items = [{"id": tc.id, "title": tc.title, "case_type": tc.case_type, "priority": tc.priority,
                          "module_id": tc.module_id,
                          "maintainer_name": member_map.get(tc.maintainer_id, "") if tc.maintainer_id else "",
                          "review_result": tc.review_result} for tc in rows]
            return json.dumps({"ok": True, "count": len(items), "cases": items}, ensure_ascii=False)

        elif action == "detail_case":
            case_id = params.get("case_id", "")
            if not case_id:
                return json.dumps({"ok": False, "message": "detail_case 需要 case_id"})
            async with sf() as session:
                tc = await session.get(FlowTestCase, case_id)
                if not tc:
                    return json.dumps({"ok": False, "message": "用例不存在"})
                maintainer_name = ""
                if tc.maintainer_id:
                    m = await session.get(Member, tc.maintainer_id)
                    maintainer_name = m.name if m else ""
                module_name = ""
                if tc.module_id:
                    mod = await session.get(FlowTestModule, tc.module_id)
                    module_name = mod.name if mod else ""
                steps = json.loads(tc.steps_json) if tc.steps_json else []
                link_count = (await session.execute(
                    select(func.count()).select_from(FlowTestCaseWorkItem)
                    .where(FlowTestCaseWorkItem.test_case_id == case_id))).scalar_one()
            return json.dumps({"ok": True, "case": {
                "id": tc.id, "project_id": tc.project_id, "module_id": tc.module_id, "module_name": module_name,
                "title": tc.title, "precondition": tc.precondition, "notes": tc.notes, "case_type": tc.case_type,
                "priority": tc.priority, "maintainer_name": maintainer_name, "review_result": tc.review_result,
                "steps": steps, "linked_work_item_count": link_count,
                "created_at": tc.created_at.isoformat() if tc.created_at else None,
            }}, ensure_ascii=False)

        # ---- Link actions ----

        elif action == "link_work_item":
            case_id = params.get("case_id", "")
            entity_type = params.get("entity_type", "")
            entity_id = params.get("entity_id", "")
            if not case_id or not entity_type or not entity_id:
                return json.dumps({"ok": False, "message": "link_work_item 需要 case_id、entity_type、entity_id"})
            async with sf() as session:
                existing = (await session.execute(select(FlowTestCaseWorkItem).where(
                    FlowTestCaseWorkItem.test_case_id == case_id, FlowTestCaseWorkItem.entity_type == entity_type,
                    FlowTestCaseWorkItem.entity_id == entity_id))).scalar_one_or_none()
                if existing:
                    return json.dumps({"ok": False, "message": "已存在相同关联"})
                link = FlowTestCaseWorkItem(test_case_id=case_id, entity_type=entity_type,
                                            entity_id=entity_id, created_by=member_id or None)
                session.add(link)
                await session.commit()
                await session.refresh(link)
            return json.dumps({"ok": True, "message": "关联已创建", "link_id": link.id}, ensure_ascii=False)

        elif action == "unlink_work_item":
            link_id = params.get("link_id", "")
            if not link_id:
                return json.dumps({"ok": False, "message": "unlink_work_item 需要 link_id"})
            async with sf() as session:
                link = await session.get(FlowTestCaseWorkItem, link_id)
                if not link:
                    return json.dumps({"ok": False, "message": "关联不存在"})
                await session.delete(link)
                await session.commit()
            return json.dumps({"ok": True, "message": "关联已删除"}, ensure_ascii=False)

        elif action == "list_links":
            case_id = params.get("case_id", "")
            entity_type = params.get("entity_type", "")
            entity_id = params.get("entity_id", "")
            if not case_id and not (entity_type and entity_id):
                return json.dumps({"ok": False, "message": "list_links 需要 case_id 或 entity_type+entity_id"})
            from openvort.plugins.vortflow.models import FlowBug, FlowStory, FlowTask
            async with sf() as session:
                stmt = select(FlowTestCaseWorkItem)
                if case_id: stmt = stmt.where(FlowTestCaseWorkItem.test_case_id == case_id)
                if entity_type and entity_id:
                    stmt = stmt.where(FlowTestCaseWorkItem.entity_type == entity_type,
                                      FlowTestCaseWorkItem.entity_id == entity_id)
                links = (await session.execute(stmt)).scalars().all()
                items = []
                model_map = {"story": FlowStory, "task": FlowTask, "bug": FlowBug}
                for link in links:
                    entity_title = ""
                    model = model_map.get(link.entity_type)
                    if model:
                        entity = await session.get(model, link.entity_id)
                        entity_title = entity.title if entity else ""
                    items.append({"link_id": link.id, "test_case_id": link.test_case_id,
                                  "entity_type": link.entity_type, "entity_id": link.entity_id,
                                  "entity_title": entity_title})
            return json.dumps({"ok": True, "count": len(items), "links": items}, ensure_ascii=False)

        return json.dumps({"ok": False, "message": f"未知操作: {action}"})
