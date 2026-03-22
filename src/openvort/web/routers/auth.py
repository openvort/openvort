"""认证路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from openvort.web.auth import authenticate_member, create_token

router = APIRouter()


class LoginRequest(BaseModel):
    user_id: str
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    user = await authenticate_member(req.user_id, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在或密码错误")

    token = create_token(
        member_id=user["member_id"],
        name=user["name"],
        roles=user["roles"],
    )
    return {
        "token": token,
        "user": user,
    }


@router.get("/me")
async def get_me():
    """供前端刷新时获取当前用户信息（需要 require_auth，但 auth 路由无全局依赖）"""
    # 这个端点实际由 /api/me/profile 替代，保留做兼容
    from fastapi import Request
    raise HTTPException(status_code=400, detail="请使用 /api/me/profile")
