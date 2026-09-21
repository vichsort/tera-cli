import pytest
from pathlib import Path
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()


def test_init_standard_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert "Project initialized successfully!" in result.output
    assert (tmp_path / "docs.yaml").exists()
    assert (tmp_path / ".teraconfig.toml").exists()

    content = (tmp_path / "docs.yaml").read_text(encoding="utf-8")
    assert "yaml-language-server: $schema=" in content
    assert "api:" in content


def test_init_complete_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--complete"])

    assert result.exit_code == 0
    assert "Project initialized successfully!" in result.output
    assert (tmp_path / "docs.yaml").exists()
    assert (tmp_path / ".teraconfig.toml").exists()


def test_init_no_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--no-config"])

    assert result.exit_code == 0
    assert (tmp_path / "docs.yaml").exists()
    assert not (tmp_path / ".teraconfig.toml").exists()


def test_init_existing_file_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    existing_file = tmp_path / "docs.yaml"
    existing_file.write_text("original content", encoding="utf-8")

    # Answer 'n' to overwrite prompt
    result = runner.invoke(app, ["init"], input="n\n")

    assert result.exit_code == 0
    assert "Operation aborted." in result.output
    assert existing_file.read_text(encoding="utf-8") == "original content"


def test_init_existing_file_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    existing_file = tmp_path / "docs.yaml"
    existing_file.write_text("original content", encoding="utf-8")

    # Answer 'y' to overwrite prompt
    result = runner.invoke(app, ["init"], input="y\n")

    assert result.exit_code == 0
    assert "Project initialized successfully!" in result.output
    assert "original content" not in existing_file.read_text(encoding="utf-8")
