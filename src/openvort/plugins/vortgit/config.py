"""VortGit 配置"""

from pydantic_settings import BaseSettings


class VortGitSettings(BaseSettings):
    """VortGit 插件配置，环境变量前缀 OPENVORT_VORTGIT_"""

    model_config = {"env_prefix": "OPENVORT_VORTGIT_"}

    # Fernet encryption key for access tokens (auto-generated if empty)
    encryption_key: str = ""

    # Coding environment
    cli_mode: str = "auto"  # auto | local | docker
    cli_docker_image: str = "ghcr.io/openvort/coding-sandbox:latest"
    cli_timeout: int = 300  # seconds
    cli_default_tool: str = "claude-code"

    # API keys for CLI coding tools (separate from OpenVort LLM config)
    claude_code_api_key: str = ""
    aider_api_key: str = ""
