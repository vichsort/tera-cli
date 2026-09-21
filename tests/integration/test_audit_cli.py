from pathlib import Path
import json
from typer.testing import CliRunner

from tera.cli.commands import app

runner = CliRunner()

CLEAN_DOCS = """
api:
  name: "Clean API"
  version: "1.0.0"

endpoints:
  - path: "/users"
    method: "GET"
    summary: "List all users"
    auth_required: true
    responses:
      success:
        status: 200
        example:
          - id: "1"
            name: "Alice"
"""

INCOHERENT_DOCS = """
api:
  name: "Incoherent API"
  version: "1.0.0"

endpoints:
  - path: "/users/{id}"
    method: "DELETE"
    summary: "Delete user"
    auth_required: false
    responses:
      success:
        status: 204
        example:
          unexpected: "body"
"""


def test_cli_audit_clean_spec(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(CLEAN_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["audit", str(doc_file)])
    assert result.exit_code == 0
    assert "Coherence Score:  100.0%" in result.output
    assert "No inconsistencies detected" in result.output


def test_cli_audit_inconsistent_spec_json(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(INCOHERENT_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["audit", str(doc_file), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total_issues"] >= 2
    assert data["critical_count"] >= 1
    assert data["coherence_score"] < 100.0


def test_cli_audit_strict_fails(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(INCOHERENT_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["audit", str(doc_file), "--strict"])
    assert result.exit_code == 1
    assert "Audit failed in strict mode" in result.output


def test_cli_audit_min_score_passes_and_fails(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(INCOHERENT_DOCS, encoding="utf-8")

    # Min score higher than actual score should fail
    result_fail = runner.invoke(app, ["audit", str(doc_file), "--min-score", "95"])
    assert result_fail.exit_code == 1
    assert "Audit failed: Coherence score" in result_fail.output

    # Min score lower than actual score should pass
    result_pass = runner.invoke(app, ["audit", str(doc_file), "--min-score", "10"])
    assert result_pass.exit_code == 0


def test_cli_audit_file_not_found() -> None:
    result = runner.invoke(app, ["audit", "non_existent.yaml"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
