import json
from pathlib import Path
from tera.services.schema import get_ir_json_schema, export_ir_json_schema, SCHEMA_ID, SCHEMA_URI


def test_get_ir_json_schema() -> None:
    schema = get_ir_json_schema()

    assert schema["$schema"] == SCHEMA_URI
    assert schema["$id"] == SCHEMA_ID
    assert schema["title"] == "TeraCanonicalIR"
    assert "properties" in schema
    assert "api" in schema["properties"]
    assert "endpoints" in schema["properties"]
    assert schema["additionalProperties"] is False


def test_export_ir_json_schema_to_string() -> None:
    json_str = export_ir_json_schema(output_path=None, indent=2)
    data = json.loads(json_str)

    assert data["title"] == "TeraCanonicalIR"
    assert "$defs" in data


def test_export_ir_json_schema_to_file(tmp_path: Path) -> None:
    out_file = tmp_path / "sub" / "schema.json"
    content = export_ir_json_schema(output_path=out_file, indent=2)

    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8").strip() == content.strip()
