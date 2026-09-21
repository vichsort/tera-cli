import pytest
from pathlib import Path
from tera.domain import TeraSchema
from tera.services import load_schema_from_source
from tera.exceptions import TeraError

def test_load_schema_from_valid_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "docs.yaml"
    yaml_file.write_text("""
api:
  name: Sample
  version: 1.0.0
endpoints: []
""", encoding="utf-8")

    schema = load_schema_from_source(yaml_file)
    assert isinstance(schema, TeraSchema)
    assert schema.api.name == "Sample"
    assert schema.api.version == "1.0.0"

def test_load_schema_from_nonexistent_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_schema_from_source("nonexistent_spec.yaml")

def test_load_schema_from_invalid_syntax(tmp_path: Path) -> None:
    invalid_file = tmp_path / "broken.yaml"
    invalid_file.write_text("api: [unclosed", encoding="utf-8")

    with pytest.raises(TeraError):
        load_schema_from_source(invalid_file)
