"""VortGit 配置"""

from pydantic_settings import BaseSettings


class VortGitSettings(BaseSettings):
    """VortGit 插件配置，环境变量前缀 OPENVORT_VORTGIT_"""

    model_config = {"env_prefix": "OPENVORT_VORTGIT_"}

    # Fernet encryption key for access tokens (auto-generated if empty)
    encryption_key: str = ""
