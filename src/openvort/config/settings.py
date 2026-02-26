"""
全局配置

基于 Pydantic BaseSettings，支持 .env 文件 + 环境变量 + 构造函数注入。
所有配置项以 OPENVORT_ 为前缀。
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM 提供商配置"""

    model_config = SettingsConfigDict(env_prefix="OPENVORT_LLM_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    provider: str = "anthropic"
    api_key: str = ""
    api_base: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    timeout: int = 120


class WeComSettings(BaseSettings):
    """企业微信 Channel 配置"""

    model_config = SettingsConfigDict(env_prefix="OPENVORT_WECOM_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    corp_id: str = ""
    app_secret: str = ""
    agent_id: str = ""
    callback_token: str = ""
    callback_aes_key: str = ""
    api_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"


class RelaySettings(BaseSettings):
    """Relay 中继配置"""

    model_config = SettingsConfigDict(env_prefix="OPENVORT_RELAY_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: str = ""  # Relay Server 地址，如 https://your-server.com
    secret: str = ""  # 鉴权密钥
    port: int = 8080  # Relay Server 监听端口（服务端用）


class ContactsSettings(BaseSettings):
    """通讯录配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_CONTACTS_", env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )

    auto_match_threshold: float = 0.9  # 自动关联置信度阈值（>= 此值自动关联，< 此值生成建议）
    sync_interval_minutes: int = 60  # 定时同步间隔（分钟），0 表示不自动同步
    admin_user_ids: str = ""  # 逗号分隔的管理员 user_id，有权执行同步/匹配管理
    role_mapping: str = "总经理:admin,副总:admin,总监:manager,经理:manager,主管:manager"  # 职位->角色映射


class Settings(BaseSettings):
    """OpenVort 全局配置"""

    model_config = SettingsConfigDict(
        env_prefix="OPENVORT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 基础
    debug: bool = False
    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".openvort")

    # 数据库
    database_url: str = "sqlite+aiosqlite:///openvort.db"

    # LLM
    llm: LLMSettings = Field(default_factory=LLMSettings)

    # 企微
    wecom: WeComSettings = Field(default_factory=WeComSettings)

    # Relay
    relay: RelaySettings = Field(default_factory=RelaySettings)

    # 通讯录
    contacts: ContactsSettings = Field(default_factory=ContactsSettings)


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
