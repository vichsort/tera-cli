# pyright: reportUnknownMemberType=false
import json
import pytest
from pathlib import Path
from typer.testing import CliRunner
from tera.cli.commands import app

runner = CliRunner()

FLASK_CODE = """
from flask import Flask

app = Flask(__name__)

def jwt_required(fn):
    return fn

@app.route("/public", methods=["GET"])
def public_route():
    return {}

@app.route("/private", methods=["GET"])
@jwt_required
def private_route():
    return {}
"""

CLEAN_DOC = """
api:
  name: Sec App
  version: "1.0.0"

endpoints:
  - path: /public
    method: GET
    summary: Public
    auth_required: false
    responses:
      success:
        status: 200
        description: OK
  - path: /private
    method: GET
    summary: Private
    auth_required: true
    responses:
      success:
        status: 200
        description: OK
"""

DRIFT_DOC = """
api:
  name: Sec App
  version: "1.0.0"

endpoints:
  - path: /public
    method: GET
    summary: Public
    auth_required: true  # DRIFT: doc says true, but code has no decorator!
    responses:
      success:
        status: 200
        description: OK
  - path: /private
    method: GET
    summary: Private
    auth_required: false  # DRIFT: doc says false, but code has jwt_required!
    responses:
      success:
        status: 200
        description: OK
"""

@pytest.fixture
def security_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path, Path]:
    app_file = tmp_path / "sec_app.py"
    app_file.write_text(FLASK_CODE, encoding="utf-8")
    clean_doc_file = tmp_path / "clean_docs.yaml"
    clean_doc_file.write_text(CLEAN_DOC, encoding="utf-8")
    drift_doc_file = tmp_path / "drift_docs.yaml"
    drift_doc_file.write_text(DRIFT_DOC, encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    return f"{app_file.stem}:app", clean_doc_file, drift_doc_file

def test_cli_security_no_drift(security_test_env: tuple[str, Path, Path]) -> None:
    app_target, clean_doc, _ = security_test_env
    result = runner.invoke(app, ["security", app_target, "--doc", str(clean_doc)])

    assert result.exit_code == 0
    assert "No security drift detected" in result.stdout

def test_cli_security_drift_detected(security_test_env: tuple[str, Path, Path]) -> None:
    app_target, _, drift_doc = security_test_env
    result = runner.invoke(app, ["security", app_target, "--doc", str(drift_doc)])

    assert result.exit_code == 0
    assert "Security Drift Audit Report" in result.stdout
    assert "[CRITICAL]" in result.stdout
    assert "critical issue(s)" in result.stdout

def test_cli_security_fail_on_drift(security_test_env: tuple[str, Path, Path]) -> None:
    app_target, _, drift_doc = security_test_env
    result = runner.invoke(app, ["security", app_target, "--doc", str(drift_doc), "--fail-on-drift"])

    assert result.exit_code == 1

def test_cli_security_json(security_test_env: tuple[str, Path, Path]) -> None:
    app_target, _, drift_doc = security_test_env
    result = runner.invoke(app, ["security", app_target, "--doc", str(drift_doc), "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["has_drift"] is True
    assert data["critical_count"] == 2
    assert len(data["issues"]) == 2
