# pyright: reportUnknownMemberType=false
from pathlib import Path
from typer.testing import CliRunner
import pytest

from tera.cli.commands import app

runner = CliRunner()


def test_cli_serve_file_not_found() -> None:
    result = runner.invoke(app, ["serve", "non_existent_docs.yaml"])
    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_cli_serve_invalid_ui(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs.yaml"
    doc_path.write_text("api:\n  name: Test\n  version: 1.0.0\nendpoints: []\n", encoding="utf-8")

    result = runner.invoke(app, ["serve", str(doc_path), "--ui", "unknown"])
    assert result.exit_code == 1
    assert "must be either 'swagger' or 'redoc'" in result.output


def test_cli_serve_invokes_run_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc_path = tmp_path / "docs.yaml"
    doc_path.write_text("api:\n  name: Test\n  version: 1.0.0\nendpoints: []\n", encoding="utf-8")

    called_args: dict[str, object] = {}

    def mock_run_server(file_path: Path, host: str, port: int, ui: str, open_browser: bool) -> None:
        called_args["file_path"] = file_path
        called_args["host"] = host
        called_args["port"] = port
        called_args["ui"] = ui
        called_args["open_browser"] = open_browser

    monkeypatch.setattr("tera.cli.commands.run_server", mock_run_server)

    result = runner.invoke(app, ["serve", str(doc_path), "--port", "9090", "--host", "0.0.0.0", "--ui", "redoc", "--open"])
    assert result.exit_code == 0
    assert "Tera Documentation Server" in result.output
    assert called_args["file_path"] == doc_path
    assert called_args["host"] == "0.0.0.0"
    assert called_args["port"] == 9090
    assert called_args["ui"] == "redoc"
    assert called_args["open_browser"] is True
