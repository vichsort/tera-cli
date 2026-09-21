import json
from pathlib import Path
from typer.testing import CliRunner
from tera.cli.commands import app

runner = CliRunner()

BASE_YAML = """
api:
  name: Test API
  version: 1.0.0
  base_url: /v1

endpoints:
  - path: /users
    method: GET
    summary: List users
    responses:
      success:
        status: 200
        description: Success
  - path: /users/{id}
    method: DELETE
    summary: Delete user
    params:
      path:
        - name: id
          type: string
          required: true
    responses:
      success:
        status: 200
        description: User deleted
"""

HEAD_YAML_BREAKING = """
api:
  name: Test API
  version: 2.0.0
  base_url: /v1

endpoints:
  - path: /users
    method: GET
    summary: List users
    responses:
      success:
        status: 200
        description: Success
  - path: /items
    method: POST
    summary: Create item
    body:
      - name: sku
        type: string
        required: true
    responses:
      success:
        status: 201
        description: Created
"""

HEAD_YAML_NON_BREAKING = """
api:
  name: Test API
  version: 1.1.0
  base_url: /v1

endpoints:
  - path: /users
    method: GET
    summary: List all users updated
    responses:
      success:
        status: 200
        description: Success
  - path: /users/{id}
    method: DELETE
    summary: Delete user
    params:
      path:
        - name: id
          type: string
          required: true
    responses:
      success:
        status: 200
        description: User deleted
  - path: /items
    method: GET
    summary: List items
    responses:
      success:
        status: 200
        description: List of items
"""

def test_cli_diff_identical_files(tmp_path: Path) -> None:
    base_file = tmp_path / "base.yaml"
    base_file.write_text(BASE_YAML, encoding="utf-8")

    result = runner.invoke(app, ["diff", str(base_file), str(base_file)])
    assert result.exit_code == 0
    assert "No differences detected" in result.stdout

def test_cli_diff_human_output_breaking(tmp_path: Path) -> None:
    base_file = tmp_path / "base.yaml"
    head_file = tmp_path / "head.yaml"
    base_file.write_text(BASE_YAML, encoding="utf-8")
    head_file.write_text(HEAD_YAML_BREAKING, encoding="utf-8")

    result = runner.invoke(app, ["diff", str(base_file), str(head_file)])
    assert result.exit_code == 0
    assert "[BREAKING]" in result.stdout
    assert "DELETE /users/{id}" in result.stdout
    assert "POST /items" in result.stdout
    assert "Summary:" in result.stdout

def test_cli_diff_json_output(tmp_path: Path) -> None:
    base_file = tmp_path / "base.yaml"
    head_file = tmp_path / "head.yaml"
    base_file.write_text(BASE_YAML, encoding="utf-8")
    head_file.write_text(HEAD_YAML_BREAKING, encoding="utf-8")

    result = runner.invoke(app, ["diff", str(base_file), str(head_file), "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["has_breaking_changes"] is True
    assert data["breaking_count"] > 0
    assert len(data["endpoint_diffs"]) == 2

def test_cli_diff_fail_on_breaking(tmp_path: Path) -> None:
    base_file = tmp_path / "base.yaml"
    head_breaking = tmp_path / "head_breaking.yaml"
    head_safe = tmp_path / "head_safe.yaml"

    base_file.write_text(BASE_YAML, encoding="utf-8")
    head_breaking.write_text(HEAD_YAML_BREAKING, encoding="utf-8")
    head_safe.write_text(HEAD_YAML_NON_BREAKING, encoding="utf-8")

    # Breaking -> exits with 1
    res_breaking = runner.invoke(app, ["diff", str(base_file), str(head_breaking), "--fail-on-breaking"])
    assert res_breaking.exit_code == 1

    # Non-breaking -> exits with 0
    res_safe = runner.invoke(app, ["diff", str(base_file), str(head_safe), "--fail-on-breaking"])
    assert res_safe.exit_code == 0

def test_cli_diff_fail_on_drift(tmp_path: Path) -> None:
    base_file = tmp_path / "base.yaml"
    head_safe = tmp_path / "head_safe.yaml"

    base_file.write_text(BASE_YAML, encoding="utf-8")
    head_safe.write_text(HEAD_YAML_NON_BREAKING, encoding="utf-8")

    # Drift exists -> exits with 1
    res_drift = runner.invoke(app, ["diff", str(base_file), str(head_safe), "--fail-on-drift"])
    assert res_drift.exit_code == 1

    # Identical -> exits with 0
    res_no_drift = runner.invoke(app, ["diff", str(base_file), str(base_file), "--fail-on-drift"])
    assert res_no_drift.exit_code == 0

def test_cli_diff_file_not_found() -> None:
    result = runner.invoke(app, ["diff", "missing_base.yaml", "missing_head.yaml"])
    assert result.exit_code == 1
    assert "Base Not Found" in result.stdout

