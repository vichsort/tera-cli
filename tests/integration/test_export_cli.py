import json
import textwrap
from pathlib import Path
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()

SAMPLE_DOCS = textwrap.dedent("""
api:
  name: Export Test API
  version: "1.0.0"
  description: Testing export command
  auth:
    type: bearer
endpoints:
  - path: /items
    method: GET
    summary: List items
    responses:
      success:
        status: 200
        description: List of items
        example: [{"id": 1}]
""")


def test_export_markdown(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")
    out_file = tmp_path / "API.md"

    result = runner.invoke(app, ["export", str(doc_file), "--format", "markdown", "-o", str(out_file)])

    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Export Test API" in content
    assert "/items" in content


def test_export_html(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")
    out_file = tmp_path / "docs.html"

    result = runner.invoke(app, ["export", str(doc_file), "--format", "html", "-o", str(out_file)])

    assert result.exit_code == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "Export Test API" in content
    assert "redoc" in content.lower()


def test_export_postman(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")
    out_file = tmp_path / "collection.json"

    result = runner.invoke(app, ["export", str(doc_file), "--format", "postman", "-o", str(out_file)])

    assert result.exit_code == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["info"]["name"] == "Export Test API"
    assert "item" in data


def test_export_invalid_format(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["export", str(doc_file), "--format", "unsupported_fmt"])

    assert result.exit_code != 0
    assert "Invalid Format" in result.output or "Unknown format" in result.output


def test_export_default_output_filename(tmp_path: Path) -> None:
    doc_file = tmp_path / "sample.yaml"
    doc_file.write_text(SAMPLE_DOCS, encoding="utf-8")

    result = runner.invoke(app, ["export", str(doc_file), "--format", "markdown"])

    assert result.exit_code == 0
    expected_out = tmp_path / "sample.md"
    assert expected_out.exists()

