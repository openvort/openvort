"""
全局配置

基于 Pydantic BaseSettings，支持 .env 文件 + 环境变量 + 构造函数注入。
所有配置项以 OPENVORT_ 为前缀。
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_project_root() -> Path:
    """Resolve project root regardless of current working directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback to historical layout: <root>/src/openvort/config/settings.py
    return current.parents[3]


_ENV_FILE = _resolve_project_root() / ".env"


class LLMModelConfig(BaseSettings):
    """单个模型配置"""

    model_config = SettingsConfigDict(extra="ignore")

    provider: str = "anthropic"
    api_key: str = ""
    api_base: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    timeout: int = 120
    api_format: str = "auto"

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "api_format": self.api_format,
        }


class LLMSettings(BaseSettings):
    """LLM 提供商配置（支持多模型 + failover）"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_LLM_", env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore",
    )

    # 主模型配置（兼容旧版环境变量）
    provider: str = "anthropic"
    api_key: str = ""
    api_base: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    timeout: int = 120
    api_format: str = "auto"

    # Failover 备选模型（JSON 字符串，如 '[{"provider":"openai","api_key":"sk-...","model":"gpt-4o"}]'）
    fallback_models: str = ""

    def get_model_chain(self) -> list[dict]:
        """返回模型链（主模型 + fallback），用于 LLMClient 初始化"""
        import json
        chain = [self._primary_dict()]
        if self.fallback_models:
            try:
                fallbacks = json.loads(self.fallback_models)
                if isinstance(fallbacks, list):
                    for fb in fallbacks:
                        cfg = LLMModelConfig(**fb)
                        chain.append(cfg.to_dict())
            except (json.JSONDecodeError, Exception):
                pass
        return chain

    def _primary_dict(self) -> dict:
        return {
            "provider": self.provider,
            "api_key": self.api_key,
            "api_base": self.api_base,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "api_format": self.api_format,
        }


class WeComSettings(BaseSettings):
    """企业微信 Channel 配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_WECOM_", env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore",
    )

    corp_id: str = ""
    app_secret: str = ""
    agent_id: str = ""
    callback_token: str = ""
    callback_aes_key: str = ""
    api_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"
    allowed_users: str = ""  # 允许处理的用户 ID，多个用逗号分隔（开发测试用）

    # Smart Robot (AI 同事) — 企微 5.0 智能机器人 API 模式
    bot_id: str = ""
    bot_secret: str = ""



class ContactsSettings(BaseSettings):
    """通讯录配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_CONTACTS_", env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore",
    )

    auto_match_threshold: float = 0.9  # 自动关联置信度阈值（>= 此值自动关联，< 此值生成建议）
    sync_interval_minutes: int = 60  # 定时同步间隔（分钟），0 表示不自动同步
    admin_user_ids: str = ""  # 逗号分隔的管理员 user_id，有权执行同步/匹配管理
    role_mapping: str = "总经理:admin,副总:admin,总监:manager,经理:manager,主管:manager"  # 职位->角色映射


class OrgSettings(BaseSettings):
    """组织管理配置（工时、时区等）"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_ORG_", env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore",
    )

    timezone: str = "Asia/Shanghai"
    work_start: str = "09:00"
    work_end: str = "18:00"
    work_days: str = "1,2,3,4,5"  # 1=Mon ... 7=Sun
    lunch_start: str = "12:00"
    lunch_end: str = "13:30"


class OpenClawSettings(BaseSettings):
    """OpenClaw 集成配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_OPENCLAW_", env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore",
    )

    gateway_url: str = ""  # OpenClaw Gateway 地址，如 http://127.0.0.1:18789
    hook_token: str = ""  # OpenClaw hooks.token（双向认证）
    enabled: bool = False  # 是否启用 OpenClaw 集成
    deliver_channel: str = "last"  # 推送到 OpenClaw 的目标通道（last/whatsapp/telegram/slack/discord 等）
    deliver_to: str = ""  # 推送目标（手机号/chat ID 等），空则用 OpenClaw 默认


class WebSettings(BaseSettings):
    """Web 管理面板配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_WEB_", env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore",
    )

    enabled: bool = True  # 是否启用 Web 面板
    port: int = 8090  # Web 面板端口
    host: str = "0.0.0.0"  # 监听地址
    default_password: str = "openvort"  # 所有成员的默认登录密码
    auto_check_update: bool = True  # 是否自动检查更新


class Settings(BaseSettings):
    """OpenVort 全局配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_",
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 基础
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".openvort")

    # 数据库
    database_url: str = "postgresql+asyncpg://openvort:openvort@localhost:5432/openvort"

    # LLM
    llm: LLMSettings = Field(default_factory=LLMSettings)

    # 企微
    wecom: WeComSettings = Field(default_factory=WeComSettings)

    # 通讯录
    contacts: ContactsSettings = Field(default_factory=ContactsSettings)

    # 组织管理
    org: OrgSettings = Field(default_factory=OrgSettings)

    # OpenClaw 集成
    openclaw: OpenClawSettings = Field(default_factory=OpenClawSettings)

    # Web 面板
    web: WebSettings = Field(default_factory=WebSettings)


# 全局单例（延迟初始化）
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def init_settings(**overrides) -> Settings:
    """初始化配置（支持覆盖）"""
    global _settings
    _settings = Settings(**overrides)
    return _settings
