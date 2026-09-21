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
    assert output_yaml.exists()

    data = yaml.safe_load(output_yaml.read_text(encoding="utf-8"))
    assert data["api"]["name"] == "FastAPI Sample App"
    paths = [ep["path"] for ep in data["endpoints"]]
    assert "/items/{item_id}" in paths


def test_scan_cli_invalid_import_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["scan", "non_existent_module:app"])

    assert result.exit_code != 0

