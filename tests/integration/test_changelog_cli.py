import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from tera.cli.commands import app

runner = CliRunner()

BASE_SPEC = """
api:
  name: Store API
  version: "1.0.0"

endpoints:
  - path: /products
    method: GET
    summary: List products
    responses:
      success:
        status: 200
        description: Products list
  - path: /products/{id}
    method: DELETE
    summary: Delete product
    responses:
      success:
        status: 200
        description: Deleted
"""

HEAD_SPEC = """
api:
  name: Store API
  version: "1.1.0"

endpoints:
  - path: /products
    method: GET
    summary: List products updated
    auth_required: true
    responses:
      success:
        status: 200
        description: Products list
  - path: /products
    method: POST
    summary: Create product
    responses:
      success:
        status: 201
        description: Created
"""

def test_cli_changelog_stdout(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["changelog", str(base), str(head)])
    assert result.exit_code == 0
    assert "## [1.1.0]" in result.stdout
    assert "### Added" in result.stdout
    assert "POST /products" in result.stdout
    assert "### Removed" in result.stdout
    assert "DELETE /products/{id}" in result.stdout
    assert "### Security" in result.stdout

def test_cli_changelog_json(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["changelog", str(base), str(head), "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["version"] == "1.1.0"
    assert len(data["added"]) > 0
    assert len(data["removed"]) > 0
    assert len(data["security"]) > 0

def test_cli_changelog_output_file(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    out = tmp_path / "RELEASE.md"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["changelog", str(base), str(head), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "## [1.1.0]" in content

def test_cli_changelog_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["changelog", str(base), str(head), "--append"])
    assert result.exit_code == 0

    changelog_file = tmp_path / "CHANGELOG.md"
    assert changelog_file.exists()
    content = changelog_file.read_text(encoding="utf-8")
    assert "# Changelog" in content
    assert "## [1.1.0]" in content

def test_cli_changelog_custom_version_and_date(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC, encoding="utf-8")

    result = runner.invoke(app, ["changelog", str(base), str(head), "--version", "2.0.0", "--date", "2026-12-31"])
    assert result.exit_code == 0
    assert "## [2.0.0] - 2026-12-31" in result.stdout
