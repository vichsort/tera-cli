import json
from pathlib import Path
from typing import Any, Dict, cast
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()


def test_schema_cli_stdout() -> None:
    result = runner.invoke(app, ["schema"])

    assert result.exit_code == 0
    data = cast(Dict[str, Any], json.loads(result.output))
    assert data["title"] == "TeraCanonicalIR"
    assert "properties" in data
    assert "api" in data["properties"]


def test_schema_cli_output_file(tmp_path: Path) -> None:
    out_file = tmp_path / "schema.json"
    result = runner.invoke(app, ["schema", "-o", str(out_file)])

    assert result.exit_code == 0
    assert out_file.exists()
    assert "exported to" in result.output
    data = cast(Dict[str, Any], json.loads(out_file.read_text(encoding="utf-8")))
    assert data["title"] == "TeraCanonicalIR"

