"""
Webhook 触发器

接收外部 HTTP 请求（CI/CD、GitHub Events、自定义触发器等），
将事件转化为 Agent 动作执行。

支持：
- 通用 webhook（POST /api/webhooks/<name>）
- 预定义模板（github、gitlab、jenkins 等）
- 自定义 payload → prompt 映射
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, Request, HTTPException

from openvort.utils.logging import get_logger

log = get_logger("web.webhooks")

webhooks_router = APIRouter()


@dataclass
class WebhookConfig:
    """单个 Webhook 配置"""
    name: str  # 标识名，如 "github-push", "jenkins-build"
    secret: str = ""  # 签名验证密钥（可选）
    action_type: str = "agent_chat"  # agent_chat | notify
    prompt_template: str = ""  # prompt 模板，支持 {event} {payload} 占位符
    channel: str = "webhook"  # 目标通道
    user_id: str = "webhook"  # 目标用户


# 全局 webhook 配置和 agent 引用
_webhooks: dict[str, WebhookConfig] = {}
_agent = None
_notify_fn = None  # 可选的通知回调


def register_webhook(config: WebhookConfig) -> None:
    """注册一个 webhook"""
    _webhooks[config.name] = config
    log.info(f"注册 Webhook: {config.name} (action={config.action_type})")


def set_webhook_runtime(agent=None, notify_fn=None) -> None:
    """注入运行时依赖"""
    global _agent, _notify_fn
    _agent = agent
    _notify_fn = notify_fn


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """验证 webhook 签名（支持 GitHub/GitLab 风格）"""
    if not secret:
        return True
    if not signature:
        return False

    # GitHub: sha256=xxx
    if signature.startswith("sha256="):
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    # GitLab: 直接比较 token
    return hmac.compare_digest(signature, secret)


# ---- 预定义 payload 解析器 ----

def _parse_github_event(headers: dict, body: dict) -> dict:
    """解析 GitHub webhook payload"""
    event_type = headers.get("x-github-event", "unknown")
    repo = body.get("repository", {}).get("full_name", "")
    sender = body.get("sender", {}).get("login", "")

    summary = f"GitHub {event_type}"
    if event_type == "push":
        ref = body.get("ref", "")
        commits = body.get("commits", [])
        summary = f"GitHub Push: {repo} ({ref}), {len(commits)} commit(s) by {sender}"
    elif event_type == "pull_request":
        action = body.get("action", "")
        pr = body.get("pull_request", {})
        summary = f"GitHub PR #{pr.get('number', '?')} {action}: {pr.get('title', '')} by {sender}"
    elif event_type == "issues":
        action = body.get("action", "")
        issue = body.get("issue", {})
        summary = f"GitHub Issue #{issue.get('number', '?')} {action}: {issue.get('title', '')} by {sender}"

    return {"event_type": event_type, "repo": repo, "sender": sender, "summary": summary}


def _parse_generic_event(headers: dict, body: dict) -> dict:
    """通用 payload 解析"""
    return {"event_type": "webhook", "summary": json.dumps(body, ensure_ascii=False)[:500]}


_parsers = {
    "github": _parse_github_event,
}


@webhooks_router.post("/{webhook_name}")
async def handle_webhook(webhook_name: str, request: Request):
    """处理 webhook 回调"""
    config = _webhooks.get(webhook_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Webhook '{webhook_name}' 未注册")

    # 读取 body
    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        body = {"raw": body_bytes.decode(errors="replace")}

    # 签名验证
    if config.secret:
        signature = (
            request.headers.get("x-hub-signature-256", "") or
            request.headers.get("x-gitlab-token", "") or
            request.headers.get("x-webhook-secret", "")
        )
        if not _verify_signature(body_bytes, signature, config.secret):
            raise HTTPException(status_code=403, detail="签名验证失败")

    # 解析事件
    headers = dict(request.headers)
    parser = _parsers.get(webhook_name.split("-")[0], _parse_generic_event)
    event_info = parser(headers, body)

    log.info(f"Webhook [{webhook_name}]: {event_info.get('summary', '')[:100]}")

    # 构建 prompt
    if config.prompt_template:
        prompt = config.prompt_template.format(
            event=event_info.get("summary", ""),
            payload=json.dumps(body, ensure_ascii=False)[:2000],
            **event_info,
        )
    else:
        prompt = f"收到外部事件通知:\n\n{event_info.get('summary', '')}\n\n请分析并给出建议。"

    # 执行动作
    if config.action_type == "agent_chat" and _agent:
        try:
            from openvort.core.context import RequestContext
            ctx = RequestContext(
                channel=config.channel, user_id=config.user_id, permissions={"*"}
            )
            reply = await _agent.process(ctx, prompt)
            return {"ok": True, "reply": reply[:500]}
        except Exception as e:
            log.error(f"Webhook agent 处理失败: {e}")
            return {"ok": False, "error": str(e)}

    elif config.action_type == "notify" and _notify_fn:
        try:
            await _notify_fn(prompt)
            return {"ok": True, "action": "notified"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return {"ok": True, "action": "received", "event": event_info.get("summary", "")}
