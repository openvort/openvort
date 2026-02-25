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

    model_config = SettingsConfigDict(env_prefix="OPENVORT_LLM_")

    provider: str = "anthropic"
    api_key: str = ""
    api_base: str = "https://api.anthropic.com"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    timeout: int = 120


class WeComSettings(BaseSettings):
    """企业微信 Channel 配置"""

    model_config = SettingsConfigDict(env_prefix="OPENVORT_WECOM_")

    corp_id: str = ""
    app_secret: str = ""
    agent_id: str = ""
    callback_token: str = ""
    callback_aes_key: str = ""
    api_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin"


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
