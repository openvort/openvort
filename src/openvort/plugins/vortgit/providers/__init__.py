"""Git provider implementations"""

from openvort.plugins.vortgit.providers.base import GitProviderBase

__all__ = ["GitProviderBase", "create_provider"]


def create_provider(platform: str, access_token: str, api_base: str = "") -> GitProviderBase:
    """Factory: create a provider client by platform name.

    Raises ValueError for unsupported platforms.
    """
    if platform == "gitee":
        from openvort.plugins.vortgit.providers.gitee import GiteeProvider
        return GiteeProvider(access_token=access_token, api_base=api_base)
    if platform == "github":
        from openvort.plugins.vortgit.providers.github import GitHubProvider
        return GitHubProvider(access_token=access_token, api_base=api_base)
    if platform == "gitlab":
        from openvort.plugins.vortgit.providers.gitlab import GitLabProvider
        return GitLabProvider(access_token=access_token, api_base=api_base)
    raise ValueError(f"Unsupported platform: {platform}")
