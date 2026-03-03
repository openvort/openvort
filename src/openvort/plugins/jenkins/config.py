"""
Jenkins plugin settings.
"""

from pydantic_settings import BaseSettings


class JenkinsSettings(BaseSettings):
    """Jenkins 插件配置，环境变量前缀 OPENVORT_JENKINS_"""

    model_config = {"env_prefix": "OPENVORT_JENKINS_"}

    url: str = ""
    username: str = ""
    api_token: str = ""
    verify_ssl: bool = True
