"""
System LLM config tool — system_llm_config

List, add, update, remove AI models and set primary/fallback via AI conversation.
"""

from openvort.plugin.base import BaseTool
from openvort.utils.logging import get_logger

log = get_logger("plugins.system.tools.llm_config")


def _mask_key(api_key: str) -> str:
    if not api_key or not isinstance(api_key, str):
        return ""
    if len(api_key) > 8:
        return api_key[:3] + "***" + api_key[-4:]
    return "***"


class SystemLLMConfigTool(BaseTool):
    name = "system_llm_config"
    description = (
        "管理 AI 模型配置：列出所有已配置的 LLM 模型及主模型/备选、查看单个模型详情、"
        "添加新模型、更新模型配置、删除模型、设置主模型与备选顺序。"
        "适用于帮助管理员通过对话添加 OpenAI/Anthropic/DeepSeek 等模型，配置后立即生效无需重启。"
    )
    required_permission = "admin"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型: list(列出所有模型及主/备选), get(查看指定模型详情), add(添加新模型), update(更新模型), remove(删除模型), set_primary(设置主模型与备选)",
                    "enum": ["list", "get", "add", "update", "remove", "set_primary"],
                },
                "model_id": {
                    "type": "string",
                    "description": "模型 ID (get/update/remove 时必填，list 返回的 id 字段)",
                },
                "provider": {
                    "type": "string",
                    "description": "提供商: anthropic | openai | deepseek | moonshot | 其他 OpenAI 兼容 (add/update 时可选)",
                },
                "model": {
                    "type": "string",
                    "description": "模型名称，如 claude-sonnet-4-20250514, gpt-4o (add 时必填, update 时可选)",
                },
                "api_key": {
                    "type": "string",
                    "description": "API Key (add 时必填，update 时可选；展示时脱敏)",
                },
                "api_base": {
                    "type": "string",
                    "description": "API 基础地址 (可选，部分厂商需自定义)",
                },
                "name": {
                    "type": "string",
                    "description": "显示名称 (可选，默认用 provider:model)",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "最大输出 token 数 (可选，默认 4096)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "请求超时秒数 (可选，默认 120)",
                },
                "primary_model_id": {
                    "type": "string",
                    "description": "主模型 ID (set_primary 时必填)",
                },
                "fallback_model_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "备选模型 ID 列表，按顺序 failover (set_primary 时可选)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, params: dict) -> str:
        try:
            from openvort.web.deps import get_config_service
        except Exception as e:
            log.warning(f"get_config_service not available: {e}")
            return "错误：当前运行环境未加载配置服务，无法管理 AI 模型。请通过 Web 管理面板的模型管理进行配置。"

        config_service = get_config_service()
        action = params.get("action", "")

        if action == "list":
            return await self._list_models(config_service)
        if action == "get":
            model_id = params.get("model_id", "").strip()
            if not model_id:
                return "错误：get 操作需要指定 model_id"
            return await self._get_model(config_service, model_id)
        if action == "add":
            return await self._add_model(config_service, params)
        if action == "update":
            model_id = params.get("model_id", "").strip()
            if not model_id:
                return "错误：update 操作需要指定 model_id"
            return await self._update_model(config_service, model_id, params)
        if action == "remove":
            model_id = params.get("model_id", "").strip()
            if not model_id:
                return "错误：remove 操作需要指定 model_id"
            return await self._remove_model(config_service, model_id)
        if action == "set_primary":
            return await self._set_primary(config_service, params)
        return f"错误：未知操作 '{action}'"

    async def _list_models(self, config_service) -> str:
        models = await config_service.get_llm_models()
        primary_id, fallback_ids = await config_service.get_llm_model_selection()
        lines = ["## 当前 AI 模型列表\n"]
        if not models:
            lines.append("尚未添加任何模型。请使用 action=add 添加（需提供 provider、model、api_key）。")
            return "\n".join(lines)
        for m in models:
            mid = m.get("id", "")
            name = m.get("name", "") or f"{m.get('provider', '')}:{m.get('model', '')}"
            role = "主模型" if mid == primary_id else ("备选" if mid in fallback_ids else "")
            key_status = "已配置" if m.get("api_key") else "未配置"
            lines.append(f"- **{name}** (id: `{mid}`)")
            lines.append(f"  provider: {m.get('provider', '')}, model: {m.get('model', '')}, API Key: {key_status} {role}")
        lines.append(f"\n主模型 ID: `{primary_id}`")
        lines.append(f"备选模型 ID 列表: {fallback_ids}")
        return "\n".join(lines)

    async def _get_model(self, config_service, model_id: str) -> str:
        models = await config_service.get_llm_models()
        target = next((m for m in models if m.get("id") == model_id), None)
        if not target:
            return f"错误：未找到 id 为 '{model_id}' 的模型"
        lines = [f"## {target.get('name', target.get('model', ''))}\n"]
        for k in ("id", "name", "provider", "model", "api_key", "api_base", "max_tokens", "timeout", "enabled", "api_format"):
            v = target.get(k)
            if k == "api_key":
                v = _mask_key(str(v or "")) or "(未设置)"
            lines.append(f"- **{k}**: {v}")
        return "\n".join(lines)

    async def _add_model(self, config_service, params: dict) -> str:
        provider = (params.get("provider") or "").strip() or "anthropic"
        model = (params.get("model") or "").strip()
        api_key = (params.get("api_key") or "").strip()
        if not model:
            return "错误：添加模型时 model 必填（如 gpt-4o、claude-sonnet-4-20250514）"
        if not api_key:
            return "错误：添加模型时 api_key 必填"
        name = (params.get("name") or "").strip()
        api_base = (params.get("api_base") or "").strip()
        max_tokens = params.get("max_tokens")
        timeout = params.get("timeout")
        new_item = {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "api_base": api_base or "",
            "name": name or f"{provider}:{model}",
        }
        if max_tokens is not None:
            new_item["max_tokens"] = int(max_tokens)
        if timeout is not None:
            new_item["timeout"] = int(timeout)
        models = await config_service.get_llm_models()
        models.append(new_item)
        await config_service.save_llm_models(models)
        # New model gets id after normalize; find it by provider+model
        models_after = await config_service.get_llm_models()
        added = next((m for m in models_after if m.get("provider") == provider and m.get("model") == model), None)
        new_id = added.get("id", "") if added else ""
        return f"已添加模型：{new_item.get('name', model)} (id: `{new_id}`)。可执行 set_primary 将其设为主模型，或通过 list 查看当前主/备选。"

    async def _update_model(self, config_service, model_id: str, params: dict) -> str:
        models = await config_service.get_llm_models()
        target = next((m for m in models if m.get("id") == model_id), None)
        if not target:
            return f"错误：未找到 id 为 '{model_id}' 的模型"
        updates = {}
        for key in ("name", "provider", "model", "api_base", "max_tokens", "timeout", "enabled", "api_format"):
            if key in params and params[key] is not None:
                if key in ("max_tokens", "timeout"):
                    updates[key] = int(params[key])
                elif key == "enabled":
                    updates[key] = bool(params[key])
                else:
                    updates[key] = params[key]
        if "api_key" in params and params["api_key"] is not None:
            v = params["api_key"]
            if isinstance(v, str) and "***" not in v and v.strip():
                updates["api_key"] = v.strip()
        target.update(updates)
        await config_service.save_llm_models(models)
        try:
            from openvort.web.routers.settings import _reload_llm_client
            primary_id, fallback_ids = await config_service.get_llm_model_selection()
            if model_id == primary_id or model_id in fallback_ids:
                await _reload_llm_client()
        except Exception as e:
            log.warning(f"Reload LLM client after update: {e}")
        return f"模型 '{target.get('name', model_id)}' 已更新。若该模型为主模型或备选，已热更新生效。"

    async def _remove_model(self, config_service, model_id: str) -> str:
        primary_id, fallback_ids = await config_service.get_llm_model_selection()
        if model_id == primary_id or model_id in fallback_ids:
            return "错误：该模型正在作为主模型或备选使用，请先用 set_primary 更换主/备选后再删除。"
        models = await config_service.get_llm_models()
        new_models = [m for m in models if m.get("id") != model_id]
        if len(new_models) == len(models):
            return f"错误：未找到 id 为 '{model_id}' 的模型"
        await config_service.save_llm_models(new_models)
        return f"已删除模型 id: {model_id}。"

    async def _set_primary(self, config_service, params: dict) -> str:
        primary_id = (params.get("primary_model_id") or "").strip()
        if not primary_id:
            return "错误：set_primary 操作需要指定 primary_model_id"
        fallback_ids = params.get("fallback_model_ids") or []
        fallback_ids = [str(x).strip() for x in fallback_ids if str(x).strip()]
        models = await config_service.get_llm_models()
        ids = {m.get("id") for m in models}
        if primary_id not in ids:
            return f"错误：主模型 id '{primary_id}' 不存在。请先用 list 查看有效 model_id。"
        for fid in fallback_ids:
            if fid not in ids:
                return f"错误：备选模型 id '{fid}' 不存在。"
        if primary_id in fallback_ids:
            fallback_ids = [x for x in fallback_ids if x != primary_id]
        await config_service.save_llm_model_selection(primary_id, fallback_ids)
        try:
            from openvort.web.routers.settings import _reload_llm_client
            await _reload_llm_client()
        except Exception as e:
            log.warning(f"Reload LLM client after set_primary: {e}")
        primary_name = next((m.get("name", m.get("model", "")) for m in models if m.get("id") == primary_id), primary_id)
        return f"已设置主模型为 {primary_name} (id: {primary_id})，备选顺序: {fallback_ids}。LLM 已热更新生效。"
