import json
import textwrap
from pathlib import Path
from typing import Any, Dict, cast
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()

VALID_SPEC = textwrap.dedent("""
api:
  name: Validation Clean API
  version: "1.0.0"
endpoints:
  - path: /ping
    method: GET
    summary: Ping
    responses:
      success:
        status: 200
""")

INVALID_SPEC = textwrap.dedent("""
api:
  title: Missing required name/version
endpoints: []
""")


def test_validate_cli_valid_human(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(VALID_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["validate", str(doc_file)])

    assert result.exit_code == 0
    assert "is a valid Tera specification" in result.output


def test_validate_cli_valid_json(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(VALID_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["validate", str(doc_file), "--json"])

    assert result.exit_code == 0
    data = cast(Dict[str, Any], json.loads(result.output))
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0


def test_validate_cli_invalid_human(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(INVALID_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["validate", str(doc_file)])

    assert result.exit_code == 1
    assert "failed schema validation" in result.output


def test_validate_cli_invalid_json(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(INVALID_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["validate", str(doc_file), "--json"])

    assert result.exit_code == 1
    data = cast(Dict[str, Any], json.loads(result.output))
    assert data["is_valid"] is False
    assert len(data["errors"]) > 0


def test_validate_cli_file_not_found() -> None:
    result = runner.invoke(app, ["validate", "non_existent_file.yaml"])

    assert result.exit_code == 1
    assert "failed schema validation" in result.output
