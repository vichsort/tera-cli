from pathlib import Path
from typing import Any, Dict, cast
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
    result = runner.invoke(app, ["import", "non_existent_spec.json"])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_cli_import_postman(tmp_path: Path) -> None:
    postman_data: Dict[str, Any] = {
        "info": {
            "name": "Imported Postman API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [
            {
                "name": "Check Health",
                "request": {
                    "method": "GET",
                    "url": {"raw": "https://api.example.com/health"},
                },
            }
        ],
    }
    spec_file = tmp_path / "collection.json"
    spec_file.write_text(json.dumps(postman_data), encoding="utf-8")
    out_file = tmp_path / "docs.yaml"

    result = runner.invoke(app, ["import", str(spec_file), "-o", str(out_file)])
    assert result.exit_code == 0
    assert "Imported 1 endpoints for 'Imported Postman API'" in result.output
    assert out_file.exists()

    content = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert content["api"]["name"] == "Imported Postman API"
    assert content["endpoints"][0]["path"] == "/health"


def test_cli_import_har(tmp_path: Path) -> None:
    har_data: Dict[str, Any] = {
        "log": {
            "version": "1.2",
            "entries": [
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/api/v1/checkout",
                        "headers": cast(list[Dict[str, str]], []),
                    },
                    "response": {
                        "status": 201,
                        "content": {"mimeType": "application/json", "text": '{"id": "ord_123"}'},
                    },
                }
            ],
        }
    }
    spec_file = tmp_path / "traffic.har"
    spec_file.write_text(json.dumps(har_data), encoding="utf-8")
    out_file = tmp_path / "docs.yaml"

    result = runner.invoke(app, ["import", str(spec_file), "-o", str(out_file)])
    assert result.exit_code == 0
    assert "Imported 1 endpoints" in result.output
    assert out_file.exists()

    content = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert content["endpoints"][0]["path"] == "/api/v1/checkout"
    assert content["endpoints"][0]["method"] == "POST"

