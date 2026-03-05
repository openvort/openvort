"""
数据库配置服务

优先级：DB > .env > 默认值
Web 面板保存到 DB，启动时从 DB 加载覆盖 settings 单例。
"""

from __future__ import annotations

import json
from uuid import uuid4
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openvort.db.models import SystemConfig
from openvort.utils.logging import get_logger

log = get_logger("config")

# LLM 配置在 DB 中的 key 前缀
_LLM_PREFIX = "llm."
_LLM_MODELS_KEY = "llm.models"
_LLM_PRIMARY_MODEL_ID_KEY = "llm.primary_model_id"
_LLM_FALLBACK_MODEL_IDS_KEY = "llm.fallback_model_ids"

# CLI 编码配置 DB keys
_CLI_DEFAULT_TOOL_KEY = "cli.default_tool"
_CLI_PRIMARY_MODEL_ID_KEY = "cli.primary_model_id"
_CLI_FALLBACK_MODEL_IDS_KEY = "cli.fallback_model_ids"
_CLI_GLOBAL_SKILLS_KEY = "cli.global_skills"

# LLM 字段 → DB key 映射
_LLM_FIELDS = {
    "provider": "llm.provider",
    "api_key": "llm.api_key",
    "api_base": "llm.api_base",
    "model": "llm.model",
    "max_tokens": "llm.max_tokens",
    "timeout": "llm.timeout",
    "fallback_models": "llm.fallback_models",
}


def _default_model_item() -> dict[str, Any]:
    return {
        "id": "",
        "name": "",
        "provider": "anthropic",
        "model": "",
        "api_key": "",
        "api_base": "",
        "max_tokens": 4096,
        "timeout": 120,
        "enabled": True,
        "api_format": "auto",
    }


def _normalize_model_item(data: dict[str, Any]) -> dict[str, Any]:
    item = _default_model_item()
    item.update(data or {})
    item["id"] = str(item.get("id") or uuid4().hex[:12])
    item["name"] = str(item.get("name") or f"{item['provider']}:{item['model']}" or f"model-{item['id'][:6]}")
    item["provider"] = str(item.get("provider") or "anthropic")
    item["model"] = str(item.get("model") or "")
    item["api_key"] = str(item.get("api_key") or "")
    item["api_base"] = str(item.get("api_base") or "")
    item["max_tokens"] = int(item.get("max_tokens") or 4096)
    item["timeout"] = int(item.get("timeout") or 120)
    item["enabled"] = bool(item.get("enabled", True))
    fmt = str(item.get("api_format") or "auto")
    item["api_format"] = fmt if fmt in ("auto", "chat_completions", "responses") else "auto"
    return item


class ConfigService:
    """数据库配置读写服务"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._sf = session_factory
        self._cache: dict[str, str] = {}

    async def load_all(self) -> dict[str, str]:
        """加载所有配置到缓存"""
        async with self._sf() as session:
            result = await session.execute(select(SystemConfig))
            rows = result.scalars().all()
            self._cache = {row.key: row.value for row in rows}
        return self._cache

    async def get(self, key: str, default: str = "") -> str:
        if key in self._cache:
            return self._cache[key]
        async with self._sf() as session:
            row = await session.get(SystemConfig, key)
            if row:
                self._cache[key] = row.value
                return row.value
        return default

    async def set(self, key: str, value: str) -> None:
        self._cache[key] = value
        async with self._sf() as session:
            row = await session.get(SystemConfig, key)
            if row:
                row.value = value
            else:
                session.add(SystemConfig(key=key, value=value))
            await session.commit()

    async def set_many(self, items: dict[str, str]) -> None:
        self._cache.update(items)
        async with self._sf() as session:
            for key, value in items.items():
                row = await session.get(SystemConfig, key)
                if row:
                    row.value = value
                else:
                    session.add(SystemConfig(key=key, value=value))
            await session.commit()

    async def _ensure_llm_model_library(self) -> dict[str, Any]:
        """确保模型库存在（兼容旧配置迁移）"""
        models_raw = self._cache.get(_LLM_MODELS_KEY, "")
        primary_id = self._cache.get(_LLM_PRIMARY_MODEL_ID_KEY, "")
        fallback_ids_raw = self._cache.get(_LLM_FALLBACK_MODEL_IDS_KEY, "")

        models: list[dict[str, Any]] = []
        fallback_ids: list[str] = []

        if models_raw:
            try:
                parsed = json.loads(models_raw)
                if isinstance(parsed, list):
                    models = [_normalize_model_item(m if isinstance(m, dict) else {}) for m in parsed]
            except (json.JSONDecodeError, Exception):
                models = []

        if fallback_ids_raw:
            try:
                parsed_fallback = json.loads(fallback_ids_raw)
                if isinstance(parsed_fallback, list):
                    fallback_ids = [str(v) for v in parsed_fallback if str(v)]
            except (json.JSONDecodeError, Exception):
                fallback_ids = []

        if models:
            model_ids = {m["id"] for m in models}
            if not primary_id or primary_id not in model_ids:
                primary_id = models[0]["id"]
            fallback_ids = [mid for mid in fallback_ids if mid in model_ids and mid != primary_id]
            await self.set_many(
                {
                    _LLM_MODELS_KEY: json.dumps(models, ensure_ascii=False),
                    _LLM_PRIMARY_MODEL_ID_KEY: primary_id,
                    _LLM_FALLBACK_MODEL_IDS_KEY: json.dumps(fallback_ids, ensure_ascii=False),
                }
            )
            return {"models": models, "primary_model_id": primary_id, "fallback_model_ids": fallback_ids}

        # 旧配置迁移 -> 新模型库
        primary = _normalize_model_item(
            {
                "id": "default-primary",
                "name": "默认主模型",
                "provider": self._cache.get("llm.provider", "anthropic"),
                "model": self._cache.get("llm.model", ""),
                "api_key": self._cache.get("llm.api_key", ""),
                "api_base": self._cache.get("llm.api_base", ""),
                "max_tokens": int(self._cache.get("llm.max_tokens", "4096") or "4096"),
                "timeout": int(self._cache.get("llm.timeout", "120") or "120"),
                "enabled": True,
            }
        )
        models = [primary]
        primary_id = primary["id"]

        fallback_raw = self._cache.get("llm.fallback_models", "")
        if fallback_raw:
            try:
                parsed_fallback_models = json.loads(fallback_raw)
                if isinstance(parsed_fallback_models, list):
                    for i, fb in enumerate(parsed_fallback_models, start=1):
                        if not isinstance(fb, dict):
                            continue
                        fallback_item = _normalize_model_item(
                            {
                                "id": f"fallback-{i}-{uuid4().hex[:6]}",
                                "name": fb.get("name") or f"备选模型 {i}",
                                **fb,
                            }
                        )
                        models.append(fallback_item)
                        fallback_ids.append(fallback_item["id"])
            except (json.JSONDecodeError, Exception):
                pass

        await self.set_many(
            {
                _LLM_MODELS_KEY: json.dumps(models, ensure_ascii=False),
                _LLM_PRIMARY_MODEL_ID_KEY: primary_id,
                _LLM_FALLBACK_MODEL_IDS_KEY: json.dumps(fallback_ids, ensure_ascii=False),
            }
        )
        log.info("已将旧版 LLM 配置迁移为模型库")
        return {"models": models, "primary_model_id": primary_id, "fallback_model_ids": fallback_ids}

    async def get_llm_models(self) -> list[dict[str, Any]]:
        lib = await self._ensure_llm_model_library()
        return lib["models"]

    async def save_llm_models(self, models: list[dict[str, Any]]) -> None:
        normalized = [_normalize_model_item(m if isinstance(m, dict) else {}) for m in models]
        await self.set(_LLM_MODELS_KEY, json.dumps(normalized, ensure_ascii=False))

    async def get_llm_model_selection(self) -> tuple[str, list[str]]:
        lib = await self._ensure_llm_model_library()
        return lib["primary_model_id"], lib["fallback_model_ids"]

    async def save_llm_model_selection(self, primary_model_id: str, fallback_model_ids: list[str]) -> None:
        models = await self.get_llm_models()
        model_ids = {m["id"] for m in models}
        if primary_model_id not in model_ids:
            raise ValueError("主模型不存在")
        cleaned = []
        seen = set()
        for model_id in fallback_model_ids:
            if model_id == primary_model_id or model_id in seen or model_id not in model_ids:
                continue
            seen.add(model_id)
            cleaned.append(model_id)
        await self.set_many(
            {
                _LLM_PRIMARY_MODEL_ID_KEY: primary_model_id,
                _LLM_FALLBACK_MODEL_IDS_KEY: json.dumps(cleaned, ensure_ascii=False),
            }
        )

    async def get_effective_llm_chain(self) -> list[dict[str, Any]]:
        lib = await self._ensure_llm_model_library()
        model_map = {m["id"]: m for m in lib["models"] if m.get("enabled", True)}
        primary = model_map.get(lib["primary_model_id"])
        if not primary:
            return []
        chain = [primary]
        for fallback_id in lib["fallback_model_ids"]:
            model = model_map.get(fallback_id)
            if model:
                chain.append(model)
        return [
            {
                "provider": item["provider"],
                "api_key": item["api_key"],
                "api_base": item["api_base"],
                "model": item["model"],
                "max_tokens": item["max_tokens"],
                "timeout": item["timeout"],
                "api_format": item.get("api_format", "auto"),
            }
            for item in chain
        ]

    async def apply_llm_to_settings(self) -> bool:
        """将 DB 中的 LLM 配置覆盖到 settings 单例，返回是否有覆盖"""
        from openvort.config.settings import get_settings
        settings = get_settings()
        applied = False

        chain = await self.get_effective_llm_chain()
        if chain:
            primary = chain[0]
            settings.llm.provider = primary["provider"]
            settings.llm.api_key = primary["api_key"]
            settings.llm.api_base = primary["api_base"]
            settings.llm.model = primary["model"]
            settings.llm.max_tokens = int(primary["max_tokens"])
            settings.llm.timeout = int(primary["timeout"])
            settings.llm.api_format = primary.get("api_format", "auto")
            settings.llm.fallback_models = json.dumps(chain[1:], ensure_ascii=False)
            applied = True
        else:
            for field, db_key in _LLM_FIELDS.items():
                value = self._cache.get(db_key)
                if value is None:
                    continue
                if field in ("max_tokens", "timeout"):
                    try:
                        setattr(settings.llm, field, int(value))
                    except ValueError:
                        continue
                else:
                    setattr(settings.llm, field, value)
                applied = True

        if applied:
            log.info("已从数据库加载 LLM 配置覆盖")
        return applied

    # ---- CLI coding model config ----

    async def get_cli_config(self) -> dict[str, Any]:
        """Get CLI coding tool + model configuration.

        Returns dict with:
          - cli_default_tool: str
          - cli_primary_model_id: str
          - cli_fallbacks: list[{tool: str, model_id: str}]
          - cli_fallback_model_ids: list[str]  (legacy compat)
        """
        await self._ensure_llm_model_library()
        default_tool = await self.get(_CLI_DEFAULT_TOOL_KEY, "claude-code")
        primary_id = await self.get(_CLI_PRIMARY_MODEL_ID_KEY, "")
        fallback_raw = await self.get(_CLI_FALLBACK_MODEL_IDS_KEY, "")
        global_skills_raw = await self.get(_CLI_GLOBAL_SKILLS_KEY, "")

        # Parse fallbacks – supports both new [{tool, model_id}] and legacy [model_id] formats
        fallbacks: list[dict[str, str]] = []
        if fallback_raw:
            try:
                parsed = json.loads(fallback_raw)
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "model_id" in item:
                            fallbacks.append({
                                "tool": item.get("tool", default_tool),
                                "model_id": str(item["model_id"]),
                            })
                        elif isinstance(item, str) and item:
                            fallbacks.append({"tool": default_tool, "model_id": item})
            except (json.JSONDecodeError, Exception):
                pass

        # Parse global skills: list of {id, name, content, enabled}
        global_skills: list[dict[str, Any]] = []
        if global_skills_raw:
            try:
                parsed_skills = json.loads(global_skills_raw)
                if isinstance(parsed_skills, list):
                    for item in parsed_skills:
                        if not isinstance(item, dict):
                            continue
                        sid = str(item.get("id") or uuid4().hex[:8])
                        name = str(item.get("name") or "Skill")
                        content = str(item.get("content") or "").strip()
                        enabled = bool(item.get("enabled", True))
                        if not content:
                            continue
                        global_skills.append(
                            {
                                "id": sid,
                                "name": name,
                                "content": content,
                                "enabled": enabled,
                            }
                        )
            except (json.JSONDecodeError, Exception):
                global_skills = []

        # If no skills configured yet, create a default Chinese-skill
        if not global_skills:
            default_skill = {
                "id": "default-zh",
                "name": "中文编码习惯",
                "content": "在进行所有编码相关的思考和回复时，始终使用简体中文进行推理和说明。",
                "enabled": True,
            }
            global_skills = [default_skill]
            await self.set(
                _CLI_GLOBAL_SKILLS_KEY,
                json.dumps(global_skills, ensure_ascii=False),
            )

        models = await self.get_llm_models()
        model_ids = {m["id"] for m in models if m.get("enabled", True)}
        if primary_id and primary_id not in model_ids:
            primary_id = ""
        fallbacks = [fb for fb in fallbacks if fb["model_id"] in model_ids]

        return {
            "cli_default_tool": default_tool,
            "cli_primary_model_id": primary_id,
            "cli_fallbacks": fallbacks,
            "cli_fallback_model_ids": [fb["model_id"] for fb in fallbacks],
            "cli_global_skills": global_skills,
        }

    async def save_cli_config(
        self,
        default_tool: str | None = None,
        primary_model_id: str | None = None,
        fallbacks: list[dict[str, str]] | None = None,
        fallback_model_ids: list[str] | None = None,
        global_skills: list[dict[str, Any]] | None = None,
    ) -> None:
        """Save CLI coding tool + model configuration.

        Accepts either `fallbacks` (new format: [{tool, model_id}])
        or `fallback_model_ids` (legacy format: [model_id]).
        """
        items: dict[str, str] = {}
        if default_tool is not None:
            items[_CLI_DEFAULT_TOOL_KEY] = default_tool
        if primary_model_id is not None:
            items[_CLI_PRIMARY_MODEL_ID_KEY] = primary_model_id

        fb_list: list[dict[str, str]] | None = None
        if fallbacks is not None:
            fb_list = fallbacks
        elif fallback_model_ids is not None:
            effective_tool = default_tool or "claude-code"
            fb_list = [{"tool": effective_tool, "model_id": mid} for mid in fallback_model_ids]

        if fb_list is not None:
            models = await self.get_llm_models()
            model_id_set = {m["id"] for m in models}
            cleaned: list[dict[str, str]] = []
            seen: set[str] = set()
            for fb in fb_list:
                mid = fb.get("model_id", "")
                if not mid or mid in seen or mid not in model_id_set:
                    continue
                seen.add(mid)
                cleaned.append({"tool": fb.get("tool", "claude-code"), "model_id": mid})
            items[_CLI_FALLBACK_MODEL_IDS_KEY] = json.dumps(cleaned, ensure_ascii=False)

        # Save global skills (normalize structure)
        if global_skills is not None:
            norm_skills: list[dict[str, Any]] = []
            for raw in global_skills:
                if not isinstance(raw, dict):
                    continue
                sid = str(raw.get("id") or uuid4().hex[:8])
                name = str(raw.get("name") or "Skill")
                content = str(raw.get("content") or "").strip()
                enabled = bool(raw.get("enabled", True))
                if not content:
                    continue
                norm_skills.append(
                    {
                        "id": sid,
                        "name": name,
                        "content": content,
                        "enabled": enabled,
                    }
                )
            items[_CLI_GLOBAL_SKILLS_KEY] = json.dumps(norm_skills, ensure_ascii=False)
        if items:
            await self.set_many(items)

    async def get_cli_model_chain(self) -> list[dict[str, Any]]:
        """Get CLI model chain (primary + fallbacks) with full model details.

        Returns list of {tool: str, model: dict} items.
        """
        cfg = await self.get_cli_config()
        models = await self.get_llm_models()
        model_map = {m["id"]: m for m in models if m.get("enabled", True)}

        chain: list[dict[str, Any]] = []
        primary = model_map.get(cfg["cli_primary_model_id"])
        if primary:
            chain.append({"tool": cfg["cli_default_tool"], "model": primary})
        for fb in cfg["cli_fallbacks"]:
            m = model_map.get(fb["model_id"])
            if m:
                chain.append({"tool": fb["tool"], "model": m})
        return chain

    async def save_llm_settings(self, data: dict[str, Any]) -> None:
        """将 LLM 配置保存到 DB 并更新 settings 单例"""
        from openvort.config.settings import get_settings
        settings = get_settings()

        items: dict[str, str] = {}
        for field, db_key in _LLM_FIELDS.items():
            if field not in data:
                continue
            value = data[field]
            if value is None:
                continue
            # api_key 脱敏值不保存
            if field == "api_key" and "***" in str(value):
                continue
            items[db_key] = str(value)
            # 同步更新 settings 单例
            if field in ("max_tokens", "timeout"):
                setattr(settings.llm, field, int(value))
            else:
                setattr(settings.llm, field, value)

        if items:
            await self.set_many(items)
            log.info(f"LLM 配置已保存到数据库: {list(items.keys())}")

        # 同步维护新模型库键，保证后续接口一致
        lib = await self._ensure_llm_model_library()
        if not lib["models"]:
            return
        primary_id = lib["primary_model_id"]
        models = lib["models"]
        for item in models:
            if item.get("id") != primary_id:
                continue
            if "provider" in data and data["provider"] is not None:
                item["provider"] = str(data["provider"])
            if "api_key" in data and data["api_key"] is not None and "***" not in str(data["api_key"]):
                item["api_key"] = str(data["api_key"])
            if "api_base" in data and data["api_base"] is not None:
                item["api_base"] = str(data["api_base"])
            if "model" in data and data["model"] is not None:
                item["model"] = str(data["model"])
            if "max_tokens" in data and data["max_tokens"] is not None:
                item["max_tokens"] = int(data["max_tokens"])
            if "timeout" in data and data["timeout"] is not None:
                item["timeout"] = int(data["timeout"])
            break
        await self.save_llm_models(models)

    # ---- Org work settings ----

    _ORG_PREFIX = "org."
    _ORG_FIELDS = ("timezone", "work_start", "work_end", "work_days", "lunch_start", "lunch_end")

    async def apply_org_to_settings(self) -> bool:
        """Apply DB org settings overrides to the settings singleton."""
        from openvort.config.settings import get_settings
        settings = get_settings()
        applied = False
        for field in self._ORG_FIELDS:
            value = self._cache.get(f"{self._ORG_PREFIX}{field}")
            if value is not None:
                setattr(settings.org, field, value)
                applied = True
        if applied:
            log.info("已从数据库加载组织工时配置覆盖")
        return applied
