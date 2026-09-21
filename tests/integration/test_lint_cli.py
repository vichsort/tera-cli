import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List, cast
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()

VALID_DOCS = textwrap.dedent("""
api:
  name: Lint Clean API
  version: "1.0.0"
  description: Valid specification
endpoints:
  - path: /status
    method: GET
    summary: Status check
    responses:
      success:
        status: 200
        description: OK
""")

INVALID_DOCS = textwrap.dedent("""
api:
  # Missing required name and version
  title: Incomplete
endpoints:
  - path: /invalid
    method: NOT_A_METHOD
""")


def test_lint_cli_valid_file_human(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(VALID_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["lint", str(doc_file)])

    assert result.exit_code == 0
    assert "No issues found" in result.output or "Passed" in result.output


def test_lint_cli_valid_file_json(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(VALID_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["lint", str(doc_file), "--json"])

    assert result.exit_code == 0
    data = cast(List[Dict[str, Any]], json.loads(result.output))
    assert isinstance(data, list)
    assert len(data) == 0


def test_lint_cli_invalid_file_human(tmp_path: Path) -> None:
    doc_file = tmp_path / "bad_docs.yaml"
    doc_file.write_text(INVALID_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["lint", str(doc_file)])

    assert result.exit_code == 1
    assert "Validation failed" in result.output or "schema_error" in result.output


def test_lint_cli_invalid_file_json(tmp_path: Path) -> None:
    doc_file = tmp_path / "bad_docs.yaml"
    doc_file.write_text(INVALID_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["lint", str(doc_file), "--json"])

    assert result.exit_code == 1
    data = cast(List[Dict[str, Any]], json.loads(result.output))
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(i["severity"] == "error" for i in data)


def test_lint_cli_file_not_found() -> None:
    result = runner.invoke(app, ["lint", "non_existent_file.yaml"])

    assert result.exit_code == 1
