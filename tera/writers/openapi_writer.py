import json
import yaml
from pathlib import Path
from tera.domain import TeraSchema
from tera.contracts import TeraWriter
from tera.adapters import TeraOpenApiAdapter

class OpenApiJsonWriter(TeraWriter):
    """
    Concrete implementation of TeraWriter.
    Recieves the Schema, converts to JSON on OpenAPI format and saves.
    """
    def __init__(self, output_path: Path):
        self.output_path = output_path

    def write(self, schema: TeraSchema) -> None:
        adapter = TeraOpenApiAdapter(schema)
        openapi_dict = adapter.convert()

        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(openapi_dict, f, indent=2, ensure_ascii=False)


class OpenApiYamlWriter(TeraWriter):
    """
    Concrete implementation of TeraWriter.
    Recieves the Schema, converts to YAML on OpenAPI format and saves.
    """
    def __init__(self, output_path: Path):
        self.output_path = output_path

    def write(self, schema: TeraSchema) -> None:
        adapter = TeraOpenApiAdapter(schema)
        openapi_dict = adapter.convert()

        with open(self.output_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                openapi_dict, 
                f, 
                sort_keys=False, 
                allow_unicode=True,
                indent=2
            )