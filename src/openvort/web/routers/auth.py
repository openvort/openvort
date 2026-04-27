"""认证路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openvort.config.settings import get_settings
from openvort.web.auth import (
    authenticate_member,
    create_token,
    TOKEN_REMEMBER_EXPIRE_HOURS,
)

router = APIRouter()


@router.get("/site-info")
async def get_site_info():
    """公开站点信息 — 登录前即可获取的配置（如是否演示模式）。

    前端在登录页调用，用于判断当前站点是否为演示站，以回填默认账号密码。
    注意：只返回公开信息，不包含任何敏感字段。
    """
    settings = get_settings()
    return {
        "is_demo": settings.is_demo,
    }


class LoginRequest(BaseModel):
    user_id: str
    password: str
    remember_me: bool = False


@router.post("/login")
async def login(req: LoginRequest):
    user = await authenticate_member(req.user_id, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或密码错误")

    expire_hours = TOKEN_REMEMBER_EXPIRE_HOURS if req.remember_me else None
    token = create_token(
        member_id=user["member_id"],
        name=user["name"],
        roles=user["roles"],
        **({"expire_hours": expire_hours} if expire_hours else {}),
    )
    return {
        "token": token,
        "user": user,
        "must_change_password": user.get("must_change_password", False),
    }


@router.get("/me")
async def get_me():
    """供前端刷新时获取当前用户信息（需要 require_auth，但 auth 路由无全局依赖）"""
    # 这个端点实际由 /api/me/profile 替代，保留做兼容
    from fastapi import Request
    raise HTTPException(status_code=400, detail="请使用 /api/me/profile")
