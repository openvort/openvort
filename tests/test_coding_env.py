"""CodingEnvironment + CLIRunner + coding tools 测试"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openvort.core.coding_env import (
    CodingEnvironment,
    EnvMode,
    EnvStatus,
    ExecResult,
)


class TestEnvMode:
    def test_values(self):
        assert EnvMode.LOCAL == "local"
        assert EnvMode.DOCKER == "docker"
        assert EnvMode.UNAVAILABLE == "unavailable"


class TestExecResult:
    def test_success(self):
        r = ExecResult(stdout="ok", exit_code=0)
        assert r.success is True

    def test_failure(self):
        r = ExecResult(stderr="err", exit_code=1)
        assert r.success is False


class TestEnvStatus:
    def test_to_dict(self):
        status = EnvStatus(mode=EnvMode.LOCAL, docker_available=True)
        d = status.to_dict()
        assert d["mode"] == "local"
        assert d["docker_available"] is True
        assert isinstance(d["cli_tools"], dict)


class TestCodingEnvironment:
    """CodingEnvironment detection and execution tests."""

    def test_detect_local_with_cli(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=False), \
             patch.object(env, "_has_any_cli_locally", return_value=True):
            assert env.detect_mode() == EnvMode.LOCAL

    def test_detect_docker_when_available(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=False), \
             patch.object(env, "_has_any_cli_locally", return_value=False), \
             patch.object(env, "_is_docker_available", return_value=True):
            assert env.detect_mode() == EnvMode.DOCKER

    def test_detect_unavailable(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=False), \
             patch.object(env, "_has_any_cli_locally", return_value=False), \
             patch.object(env, "_is_docker_available", return_value=False):
            assert env.detect_mode() == EnvMode.UNAVAILABLE

    def test_detect_inside_docker_with_socket(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=True), \
             patch.object(env, "_has_docker_socket", return_value=True):
            assert env.detect_mode() == EnvMode.DOCKER

    def test_detect_inside_docker_with_local_cli(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=True), \
             patch.object(env, "_has_docker_socket", return_value=False), \
             patch.object(env, "_has_any_cli_locally", return_value=True):
            assert env.detect_mode() == EnvMode.LOCAL

    def test_detect_inside_docker_no_socket_no_cli(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=True), \
             patch.object(env, "_has_docker_socket", return_value=False), \
             patch.object(env, "_has_any_cli_locally", return_value=False):
            assert env.detect_mode() == EnvMode.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_execute_unavailable_returns_error(self):
        env = CodingEnvironment()
        with patch.object(env, "detect_mode", return_value=EnvMode.UNAVAILABLE):
            result = await env.execute(["echo", "test"])
            assert result.exit_code == 1
            assert "not available" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_local(self):
        env = CodingEnvironment()
        result = await env._exec_local(["echo", "hello"], timeout=10)
        assert result.success
        assert "hello" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_local_timeout(self):
        env = CodingEnvironment()
        result = await env._exec_local(["sleep", "10"], timeout=1)
        assert not result.success
        assert result.exit_code == 124

    @pytest.mark.asyncio
    async def test_get_status(self):
        env = CodingEnvironment()
        with patch.object(env, "_is_running_in_docker", return_value=False), \
             patch.object(env, "_is_docker_available", return_value=False), \
             patch.object(env, "_has_docker_socket", return_value=False), \
             patch.object(env, "_has_any_cli_locally", return_value=False):
            status = await env.get_status()
            assert status.mode == EnvMode.UNAVAILABLE
            assert isinstance(status.to_dict(), dict)


class TestCLIToolSpec:
    def test_builtin_tools_registered(self):
        from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS

        assert "claude-code" in BUILTIN_CLI_TOOLS
        assert "aider" in BUILTIN_CLI_TOOLS

    def test_claude_code_spec(self):
        from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS

        spec = BUILTIN_CLI_TOOLS["claude-code"]
        assert spec.binary == "claude"
        assert spec.docker_available is True
        assert "ANTHROPIC_API_KEY" in spec.env_keys

    def test_aider_spec(self):
        from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS

        spec = BUILTIN_CLI_TOOLS["aider"]
        assert spec.binary == "aider"
        assert "--yes" in spec.run_args


class TestCLIRunner:
    def test_list_tools(self):
        from openvort.plugins.vortgit.cli_runner import CLIRunner

        runner = CLIRunner()
        tools = runner.list_tools()
        assert len(tools) >= 2
        names = [t.name for t in tools]
        assert "claude-code" in names
        assert "aider" in names

    def test_get_tool_spec(self):
        from openvort.plugins.vortgit.cli_runner import CLIRunner

        runner = CLIRunner()
        spec = runner.get_tool_spec("claude-code")
        assert spec is not None
        assert spec.display_name == "Claude Code"
        assert runner.get_tool_spec("nonexistent") is None

    def test_build_command(self):
        from openvort.plugins.vortgit.cli_runner import BUILTIN_CLI_TOOLS, CLIRunner

        runner = CLIRunner()
        spec = BUILTIN_CLI_TOOLS["claude-code"]
        cmd = runner._build_command(spec, "fix the bug")
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "fix the bug" in cmd

    @pytest.mark.asyncio
    async def test_run_unknown_tool(self):
        from openvort.plugins.vortgit.cli_runner import CLIRunner

        runner = CLIRunner()
        result = await runner.run("nonexistent", Path("/tmp"), "test")
        assert not result.success
        assert "Unknown CLI tool" in result.stderr


class TestCLIResult:
    def test_to_dict(self):
        from openvort.plugins.vortgit.cli_runner import CLIResult

        r = CLIResult(
            success=True,
            stdout="output",
            files_changed=["a.py", "b.py"],
            duration_seconds=30,
            tool_name="claude-code",
        )
        d = r.to_dict()
        assert d["success"] is True
        assert d["tool_name"] == "claude-code"
        assert len(d["files_changed"]) == 2
        assert d["duration_seconds"] == 30


class TestCodingTools:
    """Test tool schema and basic validation."""

    def test_code_task_tool_schema(self):
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        tool = CodeTaskTool()
        assert tool.name == "git_code_task"
        assert tool.required_permission == "vortgit.write"
        schema = tool.input_schema()
        assert "repo_id" in schema["properties"]
        assert "task_description" in schema["properties"]
        assert "cli_tool" in schema["properties"]
        assert "auto_pr" in schema["properties"]
        assert "repo_id" in schema["required"]
        assert "task_description" in schema["required"]

    def test_commit_push_tool_schema(self):
        from openvort.plugins.vortgit.tools.coding import CommitPushTool

        tool = CommitPushTool()
        assert tool.name == "git_commit_push"
        schema = tool.input_schema()
        assert "repo_id" in schema["required"]
        assert "commit_message" in schema["required"]

    def test_create_pr_tool_schema(self):
        from openvort.plugins.vortgit.tools.coding import CreatePRTool

        tool = CreatePRTool()
        assert tool.name == "git_create_pr"
        schema = tool.input_schema()
        assert "repo_id" in schema["required"]
        assert "title" in schema["required"]
        assert "head" in schema["required"]

    def test_to_claude_tool_format(self):
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        tool = CodeTaskTool()
        ct = tool.to_claude_tool()
        assert ct["name"] == "git_code_task"
        assert isinstance(ct["description"], str)
        assert "input_schema" in ct

    def test_generate_branch_name_bug(self):
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        name = CodeTaskTool._generate_branch_name("abc123", "", "")
        assert name == "fix/bug-abc123"

    def test_generate_branch_name_task(self):
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        name = CodeTaskTool._generate_branch_name("", "task456", "")
        assert name == "feat/task-task456"

    def test_generate_branch_name_story(self):
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        name = CodeTaskTool._generate_branch_name("", "", "story789")
        assert name == "feat/story-story789"

    def test_generate_branch_name_auto(self):
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        name = CodeTaskTool._generate_branch_name("", "", "")
        assert name.startswith("vortgit/ai-")

    def test_build_pr_body(self):
        from openvort.plugins.vortgit.cli_runner import CLIResult
        from openvort.plugins.vortgit.tools.coding import CodeTaskTool

        result = CLIResult(
            success=True,
            files_changed=["src/auth.py", "tests/test_auth.py"],
            tool_name="claude-code",
        )
        body = CodeTaskTool._build_pr_body("修复密码校验", "bug42", "", result)
        assert "修复密码校验" in body
        assert "bug42" in body
        assert "`src/auth.py`" in body
        assert "OpenVort AI" in body


class TestVortGitPluginRegistration:
    """Verify plugin properly registers new tools and permissions."""

    def test_plugin_tools_include_coding(self):
        from openvort.plugins.vortgit.plugin import VortGitPlugin

        plugin = VortGitPlugin()
        tools = plugin.get_tools()
        names = [t.name for t in tools]
        assert "git_code_task" in names
        assert "git_commit_push" in names
        assert "git_create_pr" in names

    def test_plugin_permissions_include_code(self):
        from openvort.plugins.vortgit.plugin import VortGitPlugin

        plugin = VortGitPlugin()
        perms = plugin.get_permissions()
        codes = [p["code"] for p in perms]
        assert "vortgit.code" in codes

    def test_plugin_config_schema_includes_cli(self):
        from openvort.plugins.vortgit.plugin import VortGitPlugin

        plugin = VortGitPlugin()
        schema = plugin.get_config_schema()
        keys = [s["key"] for s in schema]
        assert "cli_default_tool" in keys
        assert "claude_code_api_key" in keys
        assert "aider_api_key" in keys


class TestVortGitConfig:
    def test_default_values(self):
        with patch.dict("os.environ", {}, clear=False):
            from openvort.plugins.vortgit.config import VortGitSettings

            settings = VortGitSettings()
            assert settings.cli_mode == "auto"
            assert settings.cli_default_tool == "claude-code"
            assert settings.cli_timeout == 300
            assert settings.claude_code_api_key == ""
            assert settings.aider_api_key == ""
