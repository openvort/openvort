"""
CLI coding tool registry and unified runner.

Manages multiple CLI coding tools (Claude Code, Aider, etc.) with:
- Tool specification registry (binary, install cmd, env keys, run template)
- Availability detection
- Unified run() interface that delegates to CodingEnvironment
- Model injection: provider→env var mapping + --model CLI arg
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openvort.core.execution.coding_env import CodingEnvironment, EnvMode, ExecResult
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.cli_runner")

# Provider → env var mapping.
# CLI tools need the API key injected as specific env vars.
# For anthropic: set both API_KEY (x-api-key header) and AUTH_TOKEN (Bearer header)
# so Claude Code works with both direct Anthropic API and third-party proxies.
PROVIDER_ENV_MAP: dict[str, dict[str, str]] = {
    "anthropic": {
        "ANTHROPIC_API_KEY": "{api_key}",
        "ANTHROPIC_AUTH_TOKEN": "{api_key}",
        "ANTHROPIC_BASE_URL": "{api_base}",
    },
    "openai": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}", "OPENAI_BASE_URL": "{api_base}"},
    "deepseek": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}", "OPENAI_BASE_URL": "{api_base}"},
    "moonshot": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}", "OPENAI_BASE_URL": "{api_base}"},
    "qwen": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}", "OPENAI_BASE_URL": "{api_base}"},
    "zhipu": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}", "OPENAI_BASE_URL": "{api_base}"},
}

# Default api_base for OpenAI-compatible providers
PROVIDER_DEFAULT_API_BASE: dict[str, str] = {
    "deepseek": "https://api.deepseek.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
}


@dataclass
class CLIToolSpec:
    """Specification for a CLI coding tool."""
    name: str
    display_name: str
    binary: str
    install_cmd: str
    detect_cmd: str
    uninstall_cmd: str = ""
    env_keys: list[str] = field(default_factory=list)
    run_args: list[str] = field(default_factory=list)
    model_arg: str = "--model"
    supported_providers: list[str] = field(default_factory=lambda: [
        "anthropic", "openai", "custom", "deepseek", "moonshot", "qwen", "zhipu",
    ])
    docker_available: bool = True


BUILTIN_CLI_TOOLS: dict[str, CLIToolSpec] = {
    "claude-code": CLIToolSpec(
        name="claude-code",
        display_name="Claude Code",
        binary="claude",
        install_cmd="npm install -g @anthropic-ai/claude-code",
        detect_cmd="claude --version",
        uninstall_cmd="npm uninstall -g @anthropic-ai/claude-code",
        env_keys=["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"],
        run_args=["-p", "{prompt}", "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"],
        model_arg="--model",
        supported_providers=["anthropic", "custom"],
        docker_available=True,
    ),
    "aider": CLIToolSpec(
        name="aider",
        display_name="Aider",
        binary="aider",
        install_cmd="pip install aider-chat",
        detect_cmd="aider --version",
        uninstall_cmd="pip uninstall -y aider-chat",
        env_keys=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
        run_args=[
            "--yes-always",
            "--no-auto-commits",
            "--no-pretty",
            "--no-stream",
            "--no-check-update",
            "--no-analytics",
            "--message", "{prompt}",
        ],
        model_arg="--model",
        supported_providers=["anthropic", "openai", "custom", "deepseek", "moonshot", "qwen", "zhipu"],
        docker_available=True,
    ),
    "codex": CLIToolSpec(
        name="codex",
        display_name="Codex CLI",
        binary="codex",
        install_cmd="npm install -g @openai/codex",
        detect_cmd="codex --version",
        uninstall_cmd="npm uninstall -g @openai/codex",
        env_keys=["OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL"],
        run_args=[
            "exec",
            "--full-auto",
            "--json",
            "{prompt}",
        ],
        model_arg="--model",
        supported_providers=["openai", "custom", "deepseek", "moonshot", "qwen", "zhipu"],
        docker_available=True,
    ),
}


@dataclass
class CLIResult:
    """Result of a CLI coding tool execution."""
    success: bool = False
    stdout: str = ""
    stderr: str = ""
    files_changed: list[str] = field(default_factory=list)
    duration_seconds: int = 0
    tool_name: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "tool_name": self.tool_name,
            "files_changed": self.files_changed,
            "duration_seconds": self.duration_seconds,
            "stdout_preview": self.stdout[:2000] if self.stdout else "",
            "stderr_preview": self.stderr[:1000] if self.stderr else "",
        }


class CLIRunner:
    """Unified CLI coding tool runner."""

    def __init__(self, coding_env: CodingEnvironment | None = None):
        self._env = coding_env or CodingEnvironment()
        self._tools = dict(BUILTIN_CLI_TOOLS)

    def get_tool_spec(self, name: str) -> CLIToolSpec | None:
        return self._tools.get(name)

    def list_tools(self) -> list[CLIToolSpec]:
        return list(self._tools.values())

    def get_supported_providers(self, tool_name: str) -> list[str]:
        """Return the list of provider names this tool supports."""
        spec = self._tools.get(tool_name)
        return list(spec.supported_providers) if spec else []

    @staticmethod
    def get_tools_status() -> list[dict]:
        """Return install status for all built-in CLI tools."""
        import shutil
        import subprocess

        results: list[dict] = []
        for spec in BUILTIN_CLI_TOOLS.values():
            info: dict = {
                "name": spec.name,
                "display_name": spec.display_name,
                "binary": spec.binary,
                "install_cmd": spec.install_cmd,
                "uninstall_cmd": spec.uninstall_cmd,
                "supported_providers": spec.supported_providers,
                "installed": False,
                "version": "",
                "path": "",
            }
            path = shutil.which(spec.binary)
            if path:
                info["installed"] = True
                info["path"] = path
                try:
                    proc = subprocess.run(
                        spec.detect_cmd.split(),
                        capture_output=True, text=True, timeout=10,
                    )
                    info["version"] = proc.stdout.strip() or proc.stderr.strip()
                except Exception:
                    info["version"] = "unknown"
            results.append(info)
        return results

    async def run(
        self,
        tool_name: str,
        workspace: Path,
        prompt: str,
        *,
        model_config: dict[str, Any] | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        on_output=None,
    ) -> CLIResult:
        """Run a CLI coding tool in the workspace.

        Args:
            model_config: Model dict from the model library with keys:
                provider, model, api_key, api_base. If provided, used
                to inject the correct env vars and --model argument.
            on_output: Optional callback(line: str) for streaming stdout to caller.
        """
        spec = self._tools.get(tool_name)
        if not spec:
            return CLIResult(
                success=False,
                stderr=f"Unknown CLI tool: {tool_name}. Available: {list(self._tools.keys())}",
                tool_name=tool_name,
            )

        merged_env = dict(env or {})
        if model_config:
            self._inject_model_env(model_config, merged_env)
        else:
            self._inject_api_keys_legacy(spec, merged_env)

        if spec.name == "claude-code":
            merged_env.setdefault("API_TIMEOUT_MS", "3000000")
            merged_env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

        if spec.name == "codex":
            merged_env.setdefault("CODEX_QUIET_MODE", "1")

        command = self._build_command(spec, prompt, model_config)

        effective_timeout = timeout or self._env._timeout
        start = time.monotonic()

        model_name = (model_config or {}).get("model", "default")
        log.info(
            f"Running {spec.display_name} in {workspace} "
            f"(model={model_name}, timeout={effective_timeout}s)"
        )
        result = await self._env.execute(
            command,
            cwd=workspace,
            env=merged_env,
            timeout=effective_timeout,
            on_output=on_output,
        )
        elapsed = int(time.monotonic() - start)

        files = await self._detect_changed_files(workspace)

        cli_result = CLIResult(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            files_changed=files,
            duration_seconds=elapsed,
            tool_name=tool_name,
        )

        if cli_result.success:
            log.info(f"{spec.display_name} completed in {elapsed}s, {len(files)} files changed")
        else:
            log.warning(f"{spec.display_name} failed (exit={result.exit_code}) in {elapsed}s")

        return cli_result

    def _build_command(
        self, spec: CLIToolSpec, prompt: str,
        model_config: dict[str, Any] | None = None,
    ) -> list[str]:
        """Build the shell command from tool spec, injecting --model if configured."""
        cmd = [spec.binary]

        model_args: list[str] = []
        if model_config and model_config.get("model") and spec.model_arg:
            model_name = self._resolve_model_name(spec, model_config)
            model_args = [spec.model_arg, model_name]

        args = [arg.replace("{prompt}", prompt) for arg in spec.run_args]

        # For tools with subcommands (e.g. "codex exec ..."),
        # place subcommand before --model so the CLI parses correctly.
        if args and not args[0].startswith("-"):
            cmd.append(args.pop(0))

        cmd.extend(model_args)
        cmd.extend(args)
        return cmd

    @staticmethod
    def _resolve_model_name(spec: CLIToolSpec, model_config: dict[str, Any]) -> str:
        """Resolve the model name for the CLI tool.

        Aider requires 'openai/<model>' prefix when using OpenAI-compatible
        providers so that litellm routes the request correctly.
        """
        model = model_config.get("model", "")
        provider = model_config.get("provider", "")

        if spec.name != "aider":
            return model

        # Aider uses litellm; non-anthropic providers need openai/ prefix
        if provider == "anthropic" or model.startswith(("openai/", "anthropic/")):
            return model
        return f"openai/{model}"

    @staticmethod
    def _inject_model_env(model_config: dict[str, Any], env: dict[str, str]) -> None:
        """Inject env vars from a model library entry (provider/api_key/api_base)."""
        provider = model_config.get("provider", "")
        api_key = model_config.get("api_key", "")
        api_base = model_config.get("api_base", "")

        if not provider or not api_key:
            return

        mapping = PROVIDER_ENV_MAP.get(provider) or PROVIDER_ENV_MAP.get("openai", {})
        effective_base = api_base or PROVIDER_DEFAULT_API_BASE.get(provider, "")

        for env_key, template in mapping.items():
            if env_key in env:
                continue
            value = template.replace("{api_key}", api_key).replace("{api_base}", effective_base)
            if value:
                env[env_key] = value

    @staticmethod
    def _inject_api_keys_legacy(spec: CLIToolSpec, env: dict[str, str]) -> None:
        """Fallback: inject API keys from VortGit settings env vars (legacy)."""
        try:
            from openvort.plugins.vortgit.config import VortGitSettings
            settings = VortGitSettings()
        except Exception:
            return

        api_key = settings.claude_code_api_key or settings.aider_api_key
        key_map = {
            "ANTHROPIC_API_KEY": api_key,
            "ANTHROPIC_AUTH_TOKEN": api_key,
        }

        for key_name in spec.env_keys:
            if key_name not in env and key_name in key_map and key_map[key_name]:
                env[key_name] = key_map[key_name]

    async def _detect_changed_files(self, workspace: Path) -> list[str]:
        """Detect files changed by the CLI tool (via git status)."""
        import asyncio
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "--name-only",
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            staged_proc = await asyncio.create_subprocess_exec(
                "git", "diff", "--name-only", "--cached",
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            staged_out, _ = await asyncio.wait_for(staged_proc.communicate(), timeout=10)

            files = set()
            for line in (stdout.decode() + staged_out.decode()).strip().split("\n"):
                if line.strip():
                    files.add(line.strip())

            # Also check untracked files
            untracked_proc = await asyncio.create_subprocess_exec(
                "git", "ls-files", "--others", "--exclude-standard",
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            untracked_out, _ = await asyncio.wait_for(untracked_proc.communicate(), timeout=10)
            for line in untracked_out.decode().strip().split("\n"):
                if line.strip():
                    files.add(line.strip())

            return sorted(files)
        except Exception as e:
            log.debug(f"Failed to detect changed files: {e}")
            return []
