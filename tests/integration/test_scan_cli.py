import pytest
import textwrap
from pathlib import Path
from typer.testing import CliRunner
import yaml
from tera.main import app

runner = CliRunner()


def test_scan_cli_missing_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["scan"])

    assert result.exit_code == 1
    assert "Missing Target" in result.output


def test_scan_cli_flask_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    app_file = tmp_path / "sample_flask.py"
    app_file.write_text(
        textwrap.dedent("""
        from flask import Flask

        app = Flask("sample_flask_app")

        @app.route("/hello", methods=["GET"])
        def hello():
            \"\"\"Say hello\"\"\"
            return {"message": "Hello World"}

        @app.route("/users/<int:user_id>", methods=["GET"])
        def get_user(user_id: int):
            \"\"\"Get single user\"\"\"
            return {"id": user_id}
        """),
        encoding="utf-8",
    )

    output_yaml = tmp_path / "docs.yaml"
    result = runner.invoke(app, ["scan", "sample_flask:app", "-o", str(output_yaml)])

    assert result.exit_code == 0
    assert "Scanning Flask App: sample_flask:app" in result.output
    assert output_yaml.exists()

    data = yaml.safe_load(output_yaml.read_text(encoding="utf-8"))
    assert "api" in data
    assert "endpoints" in data
    paths = [ep["path"] for ep in data["endpoints"]]
    assert "/hello" in paths
    assert "/users/{user_id}" in paths


def test_scan_cli_fastapi_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    app_file = tmp_path / "sample_fastapi.py"
    app_file.write_text(
        textwrap.dedent("""
        class App:
            def openapi(self):
                return {
                    "openapi": "3.1.0",
                    "info": {"title": "FastAPI Sample App", "version": "2.0.0"},
                    "paths": {
                        "/items/{item_id}": {
                            "get": {
                                "summary": "Read item by ID",
                                "responses": {"200": {"description": "OK"}},
                            }
                        }
                    },
                }

        app = App()
        """),
        encoding="utf-8",
    )

    output_yaml = tmp_path / "fastapi_docs.yaml"
    result = runner.invoke(app, ["scan", "sample_fastapi:app", "-o", str(output_yaml)])

    assert result.exit_code == 0
    assert "Scanning FastAPI App: sample_fastapi:app" in result.output
    assert output_yaml.exists()

    data = yaml.safe_load(output_yaml.read_text(encoding="utf-8"))
    assert data["api"]["name"] == "FastAPI Sample App"
    paths = [ep["path"] for ep in data["endpoints"]]
    assert "/items/{item_id}" in paths


def test_scan_cli_postman_and_har(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    # Postman scanning
    postman_file = tmp_path / "collection.json"
    postman_file.write_text(
        """{"info": {"name": "Postman API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}, "item": [{"name": "Ping", "request": {"method": "GET", "url": {"raw": "https://api.example.com/ping"}}}]}""",
        encoding="utf-8",
    )
    res_pm = runner.invoke(app, ["scan", str(postman_file), "-o", str(tmp_path / "pm_docs.yaml")])
    assert res_pm.exit_code == 0
    assert "Scanning Postman Collection:" in res_pm.output

    # HAR scanning
    har_file = tmp_path / "traffic.har"
    har_file.write_text(
        """{"log": {"version": "1.2", "entries": [{"request": {"method": "GET", "url": "https://api.example.com/status"}, "response": {"status": 200}}]}}""",
        encoding="utf-8",
    )
    res_har = runner.invoke(app, ["scan", str(har_file), "-o", str(tmp_path / "har_docs.yaml")])
    assert res_har.exit_code == 0
    assert "Scanning HTTP Archive (HAR):" in res_har.output


def test_scan_cli_invalid_import_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["scan", "non_existent_module:app"])

    assert result.exit_code != 0

