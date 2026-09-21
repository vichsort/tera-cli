from pathlib import Path
import json
from typer.testing import CliRunner

from tera.cli.commands import app

runner = CliRunner()

SAMPLE_DOCS = """
api:
  name: "Store API"
  version: "1.0.0"

endpoints:
  - path: "/items"
    method: "POST"
    summary: "Create item"
    tag: "Items"
    responses:
      success:
        status: 201
        description: "Created"

  - path: "/items/{id}"
    method: "GET"
    summary: "Get item"
    tag: "Items"
    responses:
      success:
        status: 200
        description: "OK"
"""


def test_cli_graph_stdout(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["graph", str(doc_file)])
    assert result.exit_code == 0
    assert "flowchart TD" in result.output
    assert "POST__items" in result.output
    assert "GET__items__id_" in result.output


def test_cli_graph_direction_lr(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["graph", str(doc_file), "--direction", "LR"])
    assert result.exit_code == 0
    assert "flowchart LR" in result.output


def test_cli_graph_output_files(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")

    mmd_file = tmp_path / "graph.mmd"
    result = runner.invoke(app, ["graph", str(doc_file), "-o", str(mmd_file)])
    assert result.exit_code == 0
    assert mmd_file.exists()
    assert "flowchart TD" in mmd_file.read_text(encoding="utf-8")

    md_file = tmp_path / "graph.md"
    result_md = runner.invoke(app, ["graph", str(doc_file), "-o", str(md_file)])
    assert result_md.exit_code == 0
    assert md_file.exists()
    content = md_file.read_text(encoding="utf-8")
    assert "```mermaid" in content


def test_cli_graph_json(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["graph", str(doc_file), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) == 2


def test_cli_graph_file_not_found() -> None:
    result = runner.invoke(app, ["graph", "non_existent.yaml"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
