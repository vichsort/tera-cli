from pathlib import Path
from typing import Any, Dict, List, cast
import yaml


def test_pre_commit_hooks_definition() -> None:
    root_dir = Path(__file__).parent.parent.parent
    hooks_file = root_dir / ".pre-commit-hooks.yaml"

    assert hooks_file.exists(), ".pre-commit-hooks.yaml should exist in repo root"

    content = hooks_file.read_text(encoding="utf-8")
    raw_data: Any = yaml.safe_load(content)

    assert isinstance(raw_data, list), "Hooks configuration should be a list"
    hooks = cast(List[Dict[str, Any]], raw_data)

    hook_ids = [h["id"] for h in hooks]
    assert "tera-lint" in hook_ids
    assert "tera-audit" in hook_ids

    for hook in hooks:
        assert "name" in hook
        assert "entry" in hook
        assert "language" in hook
        assert hook["language"] == "python"
        assert hook["entry"].startswith("tera ")


def test_github_action_definition() -> None:
    root_dir = Path(__file__).parent.parent.parent
    action_file = root_dir / "action.yml"

    assert action_file.exists(), "action.yml should exist in repo root"

    content = action_file.read_text(encoding="utf-8")
    raw_data: Any = yaml.safe_load(content)

    assert isinstance(raw_data, dict), "Action configuration should be a dictionary"
    action = cast(Dict[str, Any], raw_data)

    assert action["name"] == "Tera CLI Action"
    assert "description" in action
    assert "inputs" in action
    inputs = cast(Dict[str, Any], action["inputs"])
    assert "command" in inputs
    assert "file" in inputs
    assert "args" in inputs

    runs = cast(Dict[str, Any], action["runs"])
    assert runs["using"] == "composite"
    assert len(runs["steps"]) >= 3
