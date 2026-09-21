import json
from pathlib import Path
from typer.testing import CliRunner
from tera.cli.commands import app

runner = CliRunner()

BASE_SPEC = """
api:
  name: My API
  version: "1.0.0"
  base_url: /v1

endpoints:
  - path: /users
    method: GET
    summary: List users
    responses:
      success:
        status: 200
        description: Success
"""

HEAD_SPEC_BREAKING = """
api:
  name: My API
  version: "1.0.0"
  base_url: /v1

endpoints: []
"""

HEAD_SPEC_MINOR = """
api:
  name: My API
  version: "1.0.0"
  base_url: /v1

endpoints:
  - path: /users
    method: GET
    summary: List users
    responses:
      success:
        status: 200
        description: Success
  - path: /products
    method: GET
    summary: List products
    responses:
      success:
        status: 200
        description: Products
"""

def test_cli_semver_human_output_major(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC_BREAKING, encoding="utf-8")

    result = runner.invoke(app, ["semver", str(base), str(head)])
    assert result.exit_code == 0
    assert "Recommended Bump: MAJOR" in result.stdout
    assert "Next Version:     2.0.0" in result.stdout
    assert "Justification:" in result.stdout

def test_cli_semver_json_output(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC_MINOR, encoding="utf-8")

    result = runner.invoke(app, ["semver", str(base), str(head), "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["bump"] == "minor"
    assert data["next_version"] == "1.1.0"
    assert len(data["reasons"]) > 0

def test_cli_semver_bump_flag(tmp_path: Path) -> None:
    base = tmp_path / "base.yaml"
    head = tmp_path / "head.yaml"
    base.write_text(BASE_SPEC, encoding="utf-8")
    head.write_text(HEAD_SPEC_MINOR, encoding="utf-8")

    result = runner.invoke(app, ["semver", str(base), str(head), "--bump"])
    assert result.exit_code == 0
    assert "Updated" in result.stdout

    updated_head = head.read_text(encoding="utf-8")
    assert 'version: "1.1.0"' in updated_head

def test_cli_semver_file_not_found() -> None:
    result = runner.invoke(app, ["semver", "missing_base.yaml", "missing_head.yaml"])
    assert result.exit_code == 1
    assert "Base Not Found" in result.stdout
