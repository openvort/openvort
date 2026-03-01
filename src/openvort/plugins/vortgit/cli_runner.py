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

from openvort.core.coding_env import CodingEnvironment, EnvMode, ExecResult
from openvort.utils.logging import get_logger

log = get_logger("plugins.vortgit.cli_runner")

# Provider → env var mapping.
# CLI tools need the API key injected as specific env vars.
PROVIDER_ENV_MAP: dict[str, dict[str, str]] = {
    "anthropic": {"ANTHROPIC_API_KEY": "{api_key}"},
    "openai": {"OPENAI_API_KEY": "{api_key}"},
    "deepseek": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}"},
    "moonshot": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}"},
    "qwen": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}"},
    "zhipu": {"OPENAI_API_KEY": "{api_key}", "OPENAI_API_BASE": "{api_base}"},
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
    env_keys: list[str] = field(default_factory=list)
    run_args: list[str] = field(default_factory=list)
    model_arg: str = "--model"
    supported_providers: list[str] = field(default_factory=lambda: [
        "anthropic", "openai", "deepseek", "moonshot", "qwen", "zhipu",
    ])
    docker_available: bool = True


BUILTIN_CLI_TOOLS: dict[str, CLIToolSpec] = {
    "claude-code": CLIToolSpec(
        name="claude-code",
        display_name="Claude Code",
        binary="claude",
        install_cmd="npm install -g @anthropic-ai/claude-code",
        detect_cmd="claude --version",
        env_keys=["ANTHROPIC_API_KEY"],
        run_args=["-p", "{prompt}", "--output-format", "stream-json", "--verbose"],
        model_arg="--model",
        supported_providers=["anthropic"],
        docker_available=True,
    ),
    "aider": CLIToolSpec(
        name="aider",
        display_name="Aider",
        binary="aider",
        install_cmd="pip install aider-chat",
        detect_cmd="aider --version",
        env_keys=["ANTHROPIC_API_KEY"],
        run_args=["--yes", "--message", "{prompt}"],
        model_arg="--model",
        supported_providers=["anthropic", "openai", "deepseek"],
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
        if model_config and model_config.get("model") and spec.model_arg:
            cmd.extend([spec.model_arg, model_config["model"]])
        for arg in spec.run_args:
            cmd.append(arg.replace("{prompt}", prompt))
        return cmd

    @staticmethod
    def _inject_model_env(model_config: dict[str, Any], env: dict[str, str]) -> None:
        """Inject env vars from a model library entry (provider/api_key/api_base)."""
        provider = model_config.get("provider", "")
        api_key = model_config.get("api_key", "")
        api_base = model_config.get("api_base", "")

        if not provider or not api_key:
            return

        mapping = PROVIDER_ENV_MAP.get(provider, {})
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

        key_map = {
            "ANTHROPIC_API_KEY": settings.claude_code_api_key or settings.aider_api_key,
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
