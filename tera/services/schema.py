import json
from pathlib import Path
from typing import Any, Dict, Optional
from tera.domain import TeraSchema

SCHEMA_ID = "https://raw.githubusercontent.com/vichsort/tera-cli/master/schemas/tera-schema.json"
SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"


def get_ir_json_schema() -> Dict[str, Any]:
    """
    Generates the official JSON Schema for Tera Canonical IR (docs.yaml).
    """
    schema = TeraSchema.model_json_schema()
    schema["$schema"] = SCHEMA_URI
    schema["$id"] = SCHEMA_ID
    schema["title"] = "TeraCanonicalIR"
    schema["description"] = "JSON Schema for Tera Canonical Intermediate Representation (IR) specification (docs.yaml)."
    return schema


def export_ir_json_schema(output_path: Optional[Path] = None, indent: int = 2) -> str:
    """
    Exports the JSON Schema to a string and optionally writes it to a file.
    """
    schema = get_ir_json_schema()
    content = json.dumps(schema, indent=indent, ensure_ascii=False)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content + "\n")
    return content
