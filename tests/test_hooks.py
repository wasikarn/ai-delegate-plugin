import subprocess
import json
import pytest
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "validate-ai-command.sh"


def run_hook(command: str) -> dict:
    """Run hook with a fake Bash tool_input and return parsed output."""
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"exit_code": result.returncode, "stdout": result.stdout}


class TestHookAllowsNonAiDelegate:
    def test_mkdir_with_ai_delegate_in_path_is_allowed(self):
        """mkdir of a path containing 'ai-delegate' must not be blocked."""
        result = run_hook("mkdir -p /path/to/ai-delegate-plugin/docs/plans")
        assert result == {}

    def test_ls_ai_delegate_dir_is_allowed(self):
        result = run_hook("ls /Users/dev/ai-delegate-plugin/src")
        assert result == {}

    def test_cat_file_in_ai_delegate_dir_is_allowed(self):
        result = run_hook("cat /home/user/ai-delegate-plugin/README.md")
        assert result == {}

    def test_grep_inside_ai_delegate_dir_is_allowed(self):
        result = run_hook("grep -r 'pattern' /path/ai-delegate-plugin/")
        assert result == {}


class TestHookBlocksInvalidAiDelegateTask:
    def test_unknown_task_is_denied(self):
        result = run_hook("ai-delegate unknown-task --file src/main.py")
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_ai_delegate_without_task_is_denied(self):
        result = run_hook("ai-delegate --file src/main.py")
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


class TestHookAllowsValidAiDelegateCommands:
    @pytest.mark.parametrize("task", ["audit", "analyze", "architecture", "refactor", "migrate", "review"])
    def test_valid_task_with_file_is_allowed(self, task):
        result = run_hook(f"ai-delegate {task} --file src/main.py")
        assert result == {}

    def test_version_flag_is_allowed(self):
        result = run_hook("ai-delegate --version")
        assert result == {}

    def test_help_flag_is_allowed(self):
        result = run_hook("ai-delegate --help")
        assert result == {}
