"""Git provider abstract base class — unified API across Gitee/GitHub/GitLab."""

from abc import ABC, abstractmethod


class GitProviderBase(ABC):
    """Git platform API abstraction.

    Each provider normalises the platform-specific REST API into a
    consistent dict-based interface so callers never touch raw responses.
    """

    name: str = ""

    @abstractmethod
    async def list_repos(
        self, *, page: int = 1, per_page: int = 20, search: str = ""
    ) -> list[dict]:
        """List repositories accessible by the configured token.

        Returns list of dicts with keys:
            name, full_name, description, clone_url, ssh_url,
            default_branch, language, private, updated_at
        """
        ...

    @abstractmethod
    async def get_repo(self, full_name: str) -> dict:
        """Get single repository detail."""
        ...

    @abstractmethod
    async def list_commits(
        self,
        full_name: str,
        *,
        branch: str = "",
        since: str = "",
        until: str = "",
        author: str = "",
        page: int = 1,
        per_page: int = 20,
    ) -> list[dict]:
        """List commits. Returns dicts with keys:
            sha, message, author_name, author_email, authored_date, additions, deletions
        """
        ...

    @abstractmethod
    async def list_branches(self, full_name: str) -> list[dict]:
        """List branches. Returns dicts: name, is_default, last_commit_sha."""
        ...

    @abstractmethod
    async def get_file_content(self, full_name: str, path: str, *, ref: str = "") -> str:
        """Get decoded file content at the given path and ref."""
        ...

    @abstractmethod
    async def get_file_tree(self, full_name: str, *, path: str = "", ref: str = "") -> list[dict]:
        """List directory entries. Returns dicts: name, path, type (file/dir), size."""
        ...

    @abstractmethod
    async def list_pull_requests(
        self, full_name: str, *, state: str = "open", page: int = 1, per_page: int = 20
    ) -> list[dict]:
        """List pull/merge requests."""
        ...

    @abstractmethod
    async def get_pull_request_detail(self, full_name: str, pr_number: int) -> dict:
        """Get single PR detail. Returns: number, title, body, state, url, head, base, created_at."""
        ...

    @abstractmethod
    async def get_pull_request_files(self, full_name: str, pr_number: int) -> list[dict]:
        """List changed files. Returns: filename, status, additions, deletions, patch."""
        ...

    @abstractmethod
    async def create_pull_request(
        self, full_name: str, *, title: str, head: str, base: str, body: str = ""
    ) -> dict:
        """Create a pull/merge request. Returns dict with: number, url, title."""
        ...

    async def close(self) -> None:
        """Release resources (httpx client, etc.)."""
        pass
