# pyright: reportUnknownMemberType=false
import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from tera.cli.commands import app

runner = CliRunner()

DUMMY_FLASK_CODE = """
from flask import Flask

app = Flask(__name__)

@app.route("/items", methods=["GET"])
def get_items():
    return []

@app.route("/items", methods=["POST"])
def create_item():
    return {}
"""

INITIAL_DOC_YAML = """
api:
  name: Sample API
  version: "1.0.0"

endpoints:
  - path: /items
    method: GET
    summary: Custom human summary
    description: Custom human description
    tag: ItemsTag
    responses:
      success:
        status: 200
        description: Success
  - path: /deleted
    method: DELETE
    summary: Endpoint removed from code
    responses:
      success:
        status: 200
        description: Success
"""

@pytest.fixture
def flask_app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    app_file = tmp_path / "sync_app.py"
    app_file.write_text(DUMMY_FLASK_CODE, encoding="utf-8")
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(INITIAL_DOC_YAML, encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    return f"{app_file.stem}:app", doc_file

def test_cli_sync_dry_run(flask_app_env: tuple[str, Path]) -> None:
    app_target, doc_file = flask_app_env
    result = runner.invoke(app, ["sync", app_target, "--doc", str(doc_file)])

    assert result.exit_code == 0
    assert "Self-Healing Sync Report" in result.stdout
    assert "POST /items" in result.stdout
    assert "Dry-run complete" in result.stdout

def test_cli_sync_json(flask_app_env: tuple[str, Path]) -> None:
    app_target, doc_file = flask_app_env
    result = runner.invoke(app, ["sync", app_target, "--doc", str(doc_file), "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data["endpoints_added"]) > 0
    assert len(data["endpoints_updated"]) > 0
    assert data["annotations_preserved"] > 0

def test_cli_sync_write_and_prune(flask_app_env: tuple[str, Path]) -> None:
    app_target, doc_file = flask_app_env
    result = runner.invoke(app, ["sync", app_target, "--doc", str(doc_file), "--write", "--prune"])

    assert result.exit_code == 0
    assert "Successfully wrote synchronized schema" in result.stdout

    updated_content = doc_file.read_text(encoding="utf-8")
    assert "Custom human summary" in updated_content
    assert "POST" in updated_content
    assert "/deleted" not in updated_content
