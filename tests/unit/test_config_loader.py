# pyright: reportPrivateUsage=false
import textwrap
from pathlib import Path
from tera.core.loader import load_config, _read_ignore_file


def test_load_config_defaults(tmp_path: Path) -> None:
    config = load_config(root_path=tmp_path)
    assert config.version == "1.0.0"
    assert config.target is None
    assert config.output is None
    assert config.format == "yaml"
    assert len(config.ignore) == 0


def test_load_config_from_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / ".teraconfig.toml"
    toml_file.write_text(
        textwrap.dedent("""
        target = "myapp.main:app"
        output = "dist/api.json"
        format = "json"
        title = "Configured API"
        version = "2.5.0"

        [lint]
        ignore = ["SEM001", "missing_description"]
        """),
        encoding="utf-8",
    )

    config = load_config(root_path=tmp_path)
    assert config.target == "myapp.main:app"
    assert config.output == Path("dist/api.json")
    assert config.format == "json"
    assert config.title == "Configured API"
    assert config.version == "2.5.0"
    assert "SEM001" in config.lint.ignore
    assert "missing_description" in config.lint.ignore


def test_load_config_corrupted_toml(tmp_path: Path) -> None:
    toml_file = tmp_path / ".teraconfig.toml"
    toml_file.write_text("invalid = [unterminated toml", encoding="utf-8")

    config = load_config(root_path=tmp_path)
    assert config.version == "1.0.0"
    assert config.target is None


def test_load_config_with_teraignore(tmp_path: Path) -> None:
    ignore_file = tmp_path / ".teraignore"
    ignore_file.write_text(
        textwrap.dedent("""
        # Comments should be ignored
        node_modules/
        *.tmp

        # Duplicate pattern
        node_modules/
        dist/
        """),
        encoding="utf-8",
    )

    config = load_config(root_path=tmp_path)
    assert "node_modules/" in config.ignore
    assert "*.tmp" in config.ignore
    assert "dist/" in config.ignore
    # Verify deduplication
    assert config.ignore.count("node_modules/") == 1


def test_read_ignore_file_missing(tmp_path: Path) -> None:
    patterns = _read_ignore_file(tmp_path / "non_existent")
    assert patterns == []
