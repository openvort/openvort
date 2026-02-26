"""
Bootstrap 专用工具 — setup_complete

AI 在初始化对话中收集完信息后调用，完成：
- 创建管理员 Member
- 分配 admin 角色
- 写入 AI 人设文件 (data/identity.md)
- 标记系统已初始化
"""

from pathlib import Path

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("core.bootstrap")


class SetupCompleteTool(BaseTool):
    """首次初始化完成工具"""

    name = "setup_complete"
    description = "完成 OpenVort 首次初始化，创建管理员并保存 AI 人设配置"

    def __init__(self, session_factory, auth_service):
        self._session_factory = session_factory
        self._auth_service = auth_service

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "admin_name": {
                    "type": "string",
                    "description": "管理员称呼/姓名",
                },
                "admin_phone": {
                    "type": "string",
                    "description": "管理员手机号（选填）",
                },
                "admin_email": {
                    "type": "string",
                    "description": "管理员邮箱（选填）",
                },
                "ai_name": {
                    "type": "string",
                    "description": "AI 助手的名字，默认小沃",
                },
                "ai_style": {
                    "type": "string",
                    "description": "AI 沟通风格描述，默认专业友好",
                },
            },
            "required": ["admin_name"],
        }

    async def execute(self, params: dict) -> str:
        admin_name = params["admin_name"]
        admin_phone = params.get("admin_phone", "")
        admin_email = params.get("admin_email", "")
        ai_name = params.get("ai_name", "小沃")
        ai_style = params.get("ai_style", "专业友好，简洁明了")

        try:
            # 1. 创建管理员 Member
            from openvort.contacts.models import Member

            member = Member(
                name=admin_name,
                email=admin_email,
                phone=admin_phone,
                status="active",
            )

            async with self._session_factory() as session:
                session.add(member)
                await session.flush()
                member_id = member.id
                await session.commit()

            log.info(f"已创建管理员: {admin_name} (id={member_id})")

            # 2. 分配 admin 角色
            await self._auth_service.assign_role(member_id, "admin")
            log.info(f"已分配 admin 角色: {member_id}")

            # 3. 写入 AI 人设文件
            identity_path = Path("data/identity.md")
            identity_path.parent.mkdir(parents=True, exist_ok=True)
            identity_content = f"""# AI 身份

名字: {ai_name}
风格: {ai_style}
管理员: {admin_name}

## 说明

这是 {ai_name} 的身份配置，在每次对话时会加载到系统提示中。
可以通过管理面板或直接编辑此文件来调整。
"""
            identity_path.write_text(identity_content, encoding="utf-8")
            log.info(f"已写入 AI 人设: {identity_path}")

            # 4. 标记系统已初始化
            from openvort.core.setup import mark_initialized

            await mark_initialized(self._session_factory, member_id)

            return (
                f"初始化完成！管理员「{admin_name}」已创建，"
                f"AI 助手「{ai_name}」已就绪。"
            )

        except Exception as e:
            log.error(f"初始化失败: {e}")
            return f"初始化失败: {e}"
