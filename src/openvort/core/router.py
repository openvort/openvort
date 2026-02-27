"""
多 Agent 路由

按通道/用户/群组路由到不同的 Agent 实例，每个 Agent 有独立的模型配置、
system prompt 和会话历史。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openvort.config.settings import LLMSettings
from openvort.core.agent import AgentRuntime
from openvort.core.session import SessionStore
from openvort.plugin.registry import PluginRegistry
from openvort.utils.logging import get_logger

log = get_logger("core.router")


@dataclass
class AgentConfig:
    """单个 Agent 的配置"""
    name: str = "default"
    model: str = ""  # 覆盖默认模型，空则用全局
    system_prompt: str = ""  # 覆盖默认 prompt，空则用全局
    max_tokens: int = 0  # 覆盖默认，0 则用全局
    # 路由匹配规则
    channels: list[str] = field(default_factory=list)  # 匹配的通道，空=全部
    user_ids: list[str] = field(default_factory=list)  # 匹配的用户 ID，空=全部
    group_ids: list[str] = field(default_factory=list)  # 匹配的群组 ID，空=全部


@dataclass
class RouteMatch:
    """路由匹配结果"""
    agent_name: str
    agent: AgentRuntime


class AgentRouter:
    """Agent 路由器

    根据配置的路由规则，将消息路由到对应的 Agent 实例。
    支持按 channel、user_id、group_id 匹配。
    未匹配到任何规则时使用默认 Agent。
    """

    def __init__(
        self,
        default_agent: AgentRuntime,
        default_llm_settings: LLMSettings,
        registry: PluginRegistry,
        session_factory=None,
    ):
        self._default_agent = default_agent
        self._default_llm = default_llm_settings
        self._registry = registry
        self._session_factory = session_factory
        self._agents: dict[str, AgentRuntime] = {"default": default_agent}
        self._configs: list[AgentConfig] = []

    def add_agent(self, config: AgentConfig) -> None:
        """注册一个 Agent 配置（延迟创建实例）"""
        self._configs.append(config)
        log.info(f"注册 Agent 路由: {config.name} (channels={config.channels}, users={config.user_ids})")

    def route(self, channel: str, user_id: str, group_id: str = "") -> RouteMatch:
        """根据通道/用户/群组匹配 Agent

        Args:
            channel: 通道名
            user_id: 用户 ID
            group_id: 群组 ID（可选）

        Returns:
            RouteMatch 包含匹配到的 Agent 名称和实例
        """
        for config in self._configs:
            if self._matches(config, channel, user_id, group_id):
                agent = self._get_or_create_agent(config)
                return RouteMatch(agent_name=config.name, agent=agent)

        return RouteMatch(agent_name="default", agent=self._default_agent)

    def _matches(self, config: AgentConfig, channel: str, user_id: str, group_id: str) -> bool:
        """检查路由规则是否匹配"""
        # channel 匹配
        if config.channels and channel not in config.channels:
            return False
        # user_id 匹配
        if config.user_ids and user_id not in config.user_ids:
            return False
        # group_id 匹配
        if config.group_ids and group_id not in config.group_ids:
            return False
        return True

    def _get_or_create_agent(self, config: AgentConfig) -> AgentRuntime:
        """获取或创建 Agent 实例"""
        if config.name in self._agents:
            return self._agents[config.name]

        # 基于默认配置创建新的 LLM 设置
        from openvort.config.settings import LLMSettings
        llm_overrides = {}
        if config.model:
            llm_overrides["model"] = config.model
        if config.max_tokens:
            llm_overrides["max_tokens"] = config.max_tokens

        if llm_overrides:
            llm_settings = LLMSettings(
                provider=self._default_llm.provider,
                api_key=self._default_llm.api_key,
                api_base=self._default_llm.api_base,
                model=llm_overrides.get("model", self._default_llm.model),
                max_tokens=llm_overrides.get("max_tokens", self._default_llm.max_tokens),
                timeout=self._default_llm.timeout,
                fallback_models=self._default_llm.fallback_models,
            )
        else:
            llm_settings = self._default_llm

        session_store = SessionStore(session_factory=self._session_factory)
        system_prompt = config.system_prompt or None

        kwargs: dict[str, Any] = {
            "llm_settings": llm_settings,
            "registry": self._registry,
            "session_store": session_store,
        }
        if system_prompt:
            kwargs["system_prompt"] = system_prompt

        agent = AgentRuntime(**kwargs)
        self._agents[config.name] = agent
        log.info(f"创建 Agent 实例: {config.name} (model={llm_settings.model})")
        return agent

    def list_agents(self) -> list[dict]:
        """列出所有已注册的 Agent 配置"""
        result = [{"name": "default", "model": self._default_llm.model, "channels": ["*"], "users": ["*"]}]
        for config in self._configs:
            result.append({
                "name": config.name,
                "model": config.model or self._default_llm.model,
                "channels": config.channels or ["*"],
                "users": config.user_ids or ["*"],
            })
        return result
