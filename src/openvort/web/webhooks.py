"""
Webhook 触发器

接收外部 HTTP 请求（CI/CD、GitHub Events、OpenClaw 等），
将事件转化为 Agent 动作执行。

支持：
- 通用 webhook（POST /api/webhooks/<name>）
- 预定义模板（github、openclaw、gitlab、jenkins 等）
- 自定义 payload → prompt 映射
- OpenClaw 双向集成（inbound + outbound）
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

from fastapi import APIRouter, Request, HTTPException

from openvort.utils.logging import get_logger

log = get_logger("web.webhooks")

webhooks_router = APIRouter()


@dataclass
class WebhookConfig:
    """单个 Webhook 配置"""
    name: str  # 标识名，如 "github-push", "openclaw", "jenkins-build"
    secret: str = ""  # 签名验证密钥（可选）
    action_type: str = "agent_chat"  # agent_chat | notify | openclaw_bridge
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
    """验证 webhook 签名（支持 GitHub/GitLab/OpenClaw 风格）"""
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

    # OpenClaw / GitLab: direct token comparison
    return hmac.compare_digest(signature, secret)


# ============ Webhook Presets (预置模板) ============

WEBHOOK_PRESETS: list[dict] = [
    {
        "id": "openclaw",
        "name": "openclaw",
        "display_name": "OpenClaw",
        "icon": "lobster",
        "featured": True,
        "description": "对接 OpenClaw 个人 AI 助手平台，让 OpenVort 的研发管理能力覆盖 WhatsApp、Telegram、Slack、Discord 等全球 IM 通道。",
        "homepage": "https://github.com/openclaw/openclaw",
        "config": {
            "action_type": "openclaw_bridge",
            "channel": "openclaw",
            "user_id": "openclaw",
            "prompt_template": "",
        },
        "guide": {
            "title": "OpenClaw × OpenVort 集成指南",
            "steps": [
                {
                    "title": "1. 安装 OpenClaw",
                    "content": "npm install -g openclaw@latest && openclaw onboard --install-daemon",
                },
                {
                    "title": "2. 配置 OpenClaw Webhook",
                    "content": (
                        '在 ~/.openclaw/openclaw.json 中启用 hooks：\n\n'
                        '```json\n'
                        '{\n'
                        '  "hooks": {\n'
                        '    "enabled": true,\n'
                        '    "token": "your-shared-secret"\n'
                        '  }\n'
                        '}\n'
                        '```'
                    ),
                },
                {
                    "title": "3. 配置 OpenVort 通道",
                    "content": (
                        "在 OpenVort 通道管理中配置 OpenClaw Channel：\n"
                        "- Gateway 地址：http://127.0.0.1:18789\n"
                        "- Hook Token：与上面 hooks.token 保持一致\n"
                        "- 投递通道：选择 OpenClaw 中已连接的 IM（如 telegram/slack/discord）"
                    ),
                },
                {
                    "title": "4. 创建此 Webhook",
                    "content": (
                        "点击「使用此模板」创建 Webhook，OpenClaw 就可以通过\n"
                        "POST /api/webhooks/openclaw 将消息转发给 OpenVort Agent。\n\n"
                        "OpenVort 处理后会通过 OpenClaw Gateway 将回复推送到用户的 IM 通道。"
                    ),
                },
            ],
            "capabilities": [
                "通过 WhatsApp/Telegram/Slack/Discord 管理项目需求和任务",
                "在任意 IM 中查询项目进度、Bug 状态",
                "通过 OpenClaw 的全球 IM 通道接收 VortFlow 状态变更通知",
                "跨平台工作汇报（Git 提交 + 任务进度联合分析）",
            ],
        },
    },
    {
        "id": "github",
        "name": "github",
        "display_name": "GitHub",
        "icon": "github",
        "featured": False,
        "description": "接收 GitHub Webhook 事件（Push、PR、Issue），触发 Agent 自动分析。",
        "homepage": "https://github.com",
        "config": {
            "action_type": "agent_chat",
            "channel": "webhook",
            "user_id": "webhook",
            "prompt_template": "收到 GitHub 事件:\n\n{event}\n\n详情:\n{payload}\n\n请分析此事件并给出建议。",
        },
        "guide": {
            "title": "GitHub Webhook 配置",
            "steps": [
                {
                    "title": "1. 在 GitHub 仓库设置中添加 Webhook",
                    "content": "Settings → Webhooks → Add webhook\nPayload URL: {server_url}/api/webhooks/github",
                },
                {
                    "title": "2. 设置签名密钥",
                    "content": "Secret 字段填写一个强密码，并在下方配置中填入相同的值。",
                },
            ],
        },
    },
    {
        "id": "gitlab",
        "name": "gitlab",
        "display_name": "GitLab",
        "icon": "gitlab",
        "featured": False,
        "description": "接收 GitLab Webhook 事件（Push、MR、Pipeline），触发 Agent 处理。",
        "homepage": "https://gitlab.com",
        "config": {
            "action_type": "agent_chat",
            "channel": "webhook",
            "user_id": "webhook",
            "prompt_template": "收到 GitLab 事件:\n\n{event}\n\n详情:\n{payload}\n\n请分析此事件并给出建议。",
        },
        "guide": {
            "title": "GitLab Webhook 配置",
            "steps": [
                {
                    "title": "1. 在 GitLab 项目设置中添加 Webhook",
                    "content": "Settings → Webhooks → Add new webhook\nURL: {server_url}/api/webhooks/gitlab",
                },
            ],
        },
    },
]


def get_presets() -> list[dict]:
    """Return all webhook presets."""
    return WEBHOOK_PRESETS


def get_preset(preset_id: str) -> dict | None:
    """Return a specific preset by ID."""
    for p in WEBHOOK_PRESETS:
        if p["id"] == preset_id:
            return p
    return None


# ============ Payload Parsers ============

def _parse_github_event(headers: dict, body: dict) -> dict:
    """Parse GitHub webhook payload."""
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


def _parse_openclaw_event(headers: dict, body: dict) -> dict:
    """Parse OpenClaw inbound webhook payload."""
    message = body.get("message", "") or body.get("text", "")
    name = body.get("name", "OpenClaw")
    source_channel = body.get("channel", "")
    sender = body.get("from", "") or body.get("sender", "") or "openclaw-user"

    summary = f"OpenClaw [{name}]"
    if source_channel:
        summary += f" via {source_channel}"
    if message:
        summary += f": {message[:200]}"

    return {
        "event_type": "openclaw",
        "sender": sender,
        "source_channel": source_channel,
        "message": message,
        "summary": summary,
    }


def _parse_gitlab_event(headers: dict, body: dict) -> dict:
    """Parse GitLab webhook payload."""
    event_type = headers.get("x-gitlab-event", "unknown")
    project = body.get("project", {}).get("path_with_namespace", "")
    user = body.get("user", {}).get("username", "") or body.get("user_username", "")

    summary = f"GitLab {event_type}"
    if "push" in event_type.lower():
        ref = body.get("ref", "")
        commits = body.get("commits", [])
        summary = f"GitLab Push: {project} ({ref}), {len(commits)} commit(s) by {user}"
    elif "merge_request" in event_type.lower():
        attrs = body.get("object_attributes", {})
        summary = f"GitLab MR !{attrs.get('iid', '?')} {attrs.get('action', '')}: {attrs.get('title', '')} by {user}"

    return {"event_type": event_type, "project": project, "sender": user, "summary": summary}


def _parse_generic_event(headers: dict, body: dict) -> dict:
    """Generic payload parser."""
    return {"event_type": "webhook", "summary": json.dumps(body, ensure_ascii=False)[:500]}


_parsers = {
    "github": _parse_github_event,
    "openclaw": _parse_openclaw_event,
    "gitlab": _parse_gitlab_event,
}


# ============ Webhook Handler ============

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
            request.headers.get("x-webhook-secret", "") or
            request.headers.get("x-openclaw-token", "")
        )
        if not _verify_signature(body_bytes, signature, config.secret):
            raise HTTPException(status_code=403, detail="签名验证失败")

    # 解析事件
    headers = dict(request.headers)
    parser = _parsers.get(webhook_name.split("-")[0], _parse_generic_event)
    event_info = parser(headers, body)

    log.info(f"Webhook [{webhook_name}]: {event_info.get('summary', '')[:100]}")

    # ---- OpenClaw bridge: forward to OpenClaw Channel ----
    if config.action_type == "openclaw_bridge":
        try:
            from openvort.web.deps import get_registry
            registry = get_registry()
            oc_channel = registry.get_channel("openclaw")
            if oc_channel and hasattr(oc_channel, "handle_callback"):
                reply = await oc_channel.handle_callback(body, headers)
                if reply:
                    from openvort.plugin.base import Message as Msg
                    await oc_channel.send(
                        event_info.get("sender", "openclaw-user"),
                        Msg(content=reply, channel="openclaw"),
                    )
                return {"ok": True, "reply": (reply or "")[:500]}
            else:
                log.warning("OpenClaw Channel 未配置或未启动")
                return {"ok": False, "error": "OpenClaw Channel not configured"}
        except Exception as e:
            log.error(f"OpenClaw bridge 处理失败: {e}")
            return {"ok": False, "error": str(e)}

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


# ============ OpenClaw Outbound Push ============

async def push_to_openclaw(event: str, detail: str, gateway_url: str = "", hook_token: str = "") -> bool:
    """Push an event notification to OpenClaw Gateway.

    Called by Notifier or other modules when VortFlow state changes
    need to be broadcast to OpenClaw-connected IM channels.
    """
    if not gateway_url or not hook_token:
        try:
            from openvort.config.settings import get_settings
            s = get_settings().openclaw
            gateway_url = gateway_url or (s.gateway_url.rstrip("/") if s.gateway_url else "")
            hook_token = hook_token or s.hook_token
        except Exception:
            pass

    if not gateway_url or not hook_token:
        return False

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{gateway_url}/hooks/agent",
                headers={
                    "Authorization": f"Bearer {hook_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "message": f"[OpenVort] {event}\n\n{detail}",
                    "name": "OpenVort",
                    "deliver": True,
                    "channel": "last",
                },
            )
            return resp.status_code in (200, 202)
    except Exception as e:
        log.warning(f"推送到 OpenClaw 失败: {e}")
        return False
