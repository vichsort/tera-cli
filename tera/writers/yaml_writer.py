import yaml
from pathlib import Path
from tera.domain import TeraSchema
from tera.contracts import TeraWriter

class YamlFileWriter(TeraWriter):
    """
    Concrete implementation of TeraWriter.
    Recieves the Schema, converts to YAML and saves.
    """
    def __init__(self, output_path: Path):
        self.output_path = output_path

    def write(self, schema: TeraSchema) -> None:
        data = schema.dict(exclude_none=True)

        with open(self.output_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                data, 
                f, 
                sort_keys=False, 
                allow_unicode=True, 
                default_flow_style=False,
                indent=2
            )