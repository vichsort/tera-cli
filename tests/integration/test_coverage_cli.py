import json
from pathlib import Path
from typer.testing import CliRunner
from tera.cli.commands import app

runner = CliRunner()

COMPLETE_DOC = """
api:
  name: Complete API
  version: "1.0.0"

endpoints:
  - path: /users
    method: GET
    summary: List users
    description: Returns list of registered users
    params:
      query:
        - name: limit
          type: integer
          description: Maximum number of records to return
    responses:
      success:
        status: 200
        description: Success
      errors:
        - status: 400
          message: Bad Request
"""

INCOMPLETE_DOC = """
api:
  name: Incomplete API
  version: "1.0.0"

endpoints:
  - path: /users
    method: GET
    summary: ""
    responses:
      success:
        status: 200
        description: Success
"""

def test_cli_coverage_human_output(tmp_path: Path) -> None:
    doc = tmp_path / "docs.yaml"
    doc.write_text(COMPLETE_DOC, encoding="utf-8")

    result = runner.invoke(app, ["coverage", str(doc)])
    assert result.exit_code == 0
    assert "Documentation Coverage Report" in result.stdout
    assert "Overall Documentation Coverage: 100.0%" in result.stdout

def test_cli_coverage_json_output(tmp_path: Path) -> None:
    doc = tmp_path / "docs.yaml"
    doc.write_text(INCOMPLETE_DOC, encoding="utf-8")

    result = runner.invoke(app, ["coverage", str(doc), "--json"])
    assert result.exit_code == 0

    data = json.loads(result.stdout)
    assert data["total_endpoints"] == 1
    assert data["overall_score"] < 50.0
    assert "summary_stats" in data

def test_cli_coverage_min_threshold_passes(tmp_path: Path) -> None:
    doc = tmp_path / "docs.yaml"
    doc.write_text(COMPLETE_DOC, encoding="utf-8")

    result = runner.invoke(app, ["coverage", str(doc), "--min-coverage", "90"])
    assert result.exit_code == 0

def test_cli_coverage_min_threshold_fails(tmp_path: Path) -> None:
    doc = tmp_path / "docs.yaml"
    doc.write_text(INCOMPLETE_DOC, encoding="utf-8")

    result = runner.invoke(app, ["coverage", str(doc), "--min-coverage", "80"])
    assert result.exit_code == 1
    assert "Coverage check failed" in result.stdout

