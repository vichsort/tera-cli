from pathlib import Path
from typing import Any, Dict
import json
from typer.testing import CliRunner
import yaml

from tera.cli.commands import app

runner = CliRunner()


def test_cli_import_openapi_json(tmp_path: Path) -> None:
    spec: Dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Imported API", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {
                    "summary": "Ping service",
                    "responses": {"200": {"description": "Pong"}},
                }
            }
        },
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    out_file = tmp_path / "docs.yaml"

    result = runner.invoke(app, ["import", str(spec_file), "-o", str(out_file)])
    assert result.exit_code == 0
    assert "Imported 1 endpoints" in result.output
    assert out_file.exists()

    content = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert content["api"]["name"] == "Imported API"
    assert len(content["endpoints"]) == 1
    assert content["endpoints"][0]["path"] == "/ping"


def test_cli_import_json_stdout(tmp_path: Path) -> None:
    spec: Dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Stdout API", "version": "1.0.0"},
        "paths": {
            "/status": {
                "get": {
                    "summary": "Get status",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")

    result = runner.invoke(app, ["import", str(spec_file), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["api"]["name"] == "Stdout API"
    assert len(data["endpoints"]) == 1


def test_cli_import_file_exists_and_force(tmp_path: Path) -> None:
    spec: Dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Force API", "version": "1.0.0"},
        "paths": {},
    }
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    out_file = tmp_path / "docs.yaml"
    out_file.write_text("existing content", encoding="utf-8")

    # Should fail without --force
    res_fail = runner.invoke(app, ["import", str(spec_file), "-o", str(out_file)])
    assert res_fail.exit_code == 1
    assert "already exists" in res_fail.output

    # Should succeed with --force
    res_ok = runner.invoke(app, ["import", str(spec_file), "-o", str(out_file), "--force"])
    assert res_ok.exit_code == 0
    assert "Imported 0 endpoints" in res_ok.output


def test_cli_import_file_not_found() -> None:
    result = runner.invoke(app, ["import", "non_existent_openapi.json"])
    assert result.exit_code == 1
    assert "does not exist" in result.output

