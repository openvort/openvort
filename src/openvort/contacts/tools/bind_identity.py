"""
身份绑定工具 — contacts_bind_identity

用户自助将自己与某平台账号关联。
防冒领验证：名称匹配 + 手机号/邮箱辅助确认。
"""

from sqlalchemy import select

from openvort.contacts.models import Member, PlatformIdentity
from openvort.db.engine import get_session_factory
from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("contacts.tools.bind_identity")


class BindIdentityTool(BaseTool):
    """自助绑定平台身份"""

    name = "contacts_bind_identity"
    description = "将当前用户与指定平台的账号绑定（如绑定禅道账号），需验证身份防止冒领"
    required_permission = ""  # 所有人可用

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "description": "平台标识，如 zentao、gitee",
                },
                "account": {
                    "type": "string",
                    "description": "用户在该平台的账号名或登录名",
                },
            },
            "required": ["platform", "account"],
        }

    async def execute(self, params: dict) -> str:
        platform = params["platform"]
        account = params["account"]
        member_id = params.get("_member_id")
        caller_id = params.get("_caller_id", "")

        if not member_id:
            return "无法识别你的身份，请先通过通讯录同步或联系管理员。"

        session_factory = get_session_factory()
        async with session_factory() as session:
            # 1. 查找目标平台身份
            stmt = select(PlatformIdentity).where(
                PlatformIdentity.platform == platform,
                PlatformIdentity.platform_user_id == account,
            )
            result = await session.execute(stmt)
            target_identity = result.scalars().first()

            if not target_identity:
                # 尝试按 username 匹配
                stmt2 = select(PlatformIdentity).where(
                    PlatformIdentity.platform == platform,
                    PlatformIdentity.platform_username == account,
                )
                result2 = await session.execute(stmt2)
                target_identity = result2.scalars().first()

            if not target_identity:
                return (
                    f"在 {platform} 通讯录中未找到账号「{account}」。"
                    f"请确认账号名是否正确，或联系管理员先同步 {platform} 通讯录。"
                )

            # 2. 检查是否已被其他人绑定
            if target_identity.member_id and target_identity.member_id != member_id:
                return (
                    f"{platform} 账号「{account}」已被其他成员关联，"
                    f"如有疑问请联系管理员处理。"
                )

            # 3. 检查是否已经绑定（幂等）
            if target_identity.member_id == member_id:
                return f"你已经绑定了 {platform} 账号「{account}」，无需重复操作。"

            # 4. 防冒领验证：名称匹配
            current_member = await session.get(Member, member_id)
            if not current_member:
                return "无法获取你的成员信息，请联系管理员。"

            target_name = target_identity.platform_display_name or target_identity.platform_username
            name_match = _name_similar(current_member.name, target_name)

            # 名称匹配 → 直接绑定
            if name_match:
                target_identity.member_id = member_id
                await session.commit()
                log.info(f"身份绑定成功: member={member_id} -> {platform}:{account}")
                return f"绑定成功！你的 {platform} 账号已关联为「{account}」。"

            # 名称不匹配，尝试手机号/邮箱辅助验证
            phone_match = (
                current_member.phone
                and target_identity.platform_phone
                and current_member.phone == target_identity.platform_phone
            )
            email_match = (
                current_member.email
                and target_identity.platform_email
                and current_member.email == target_identity.platform_email
            )

            if phone_match or email_match:
                target_identity.member_id = member_id
                await session.commit()
                match_by = "手机号" if phone_match else "邮箱"
                log.info(f"身份绑定成功(通过{match_by}): member={member_id} -> {platform}:{account}")
                return f"通过{match_by}验证，绑定成功！你的 {platform} 账号已关联为「{account}」。"

            # 都不匹配 → 拒绝，建议联系管理员
            return (
                f"你的名称「{current_member.name}」与 {platform} 账号「{account}」"
                f"（{target_name}）不一致，且无法通过手机号/邮箱验证。"
                f"为安全起见，请联系管理员手动关联。"
            )


def _name_similar(name_a: str, name_b: str) -> bool:
    """简单名称匹配：完全一致或互相包含"""
    if not name_a or not name_b:
        return False
    a = name_a.strip().lower()
    b = name_b.strip().lower()
    return a == b or a in b or b in a
