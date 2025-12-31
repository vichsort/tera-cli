import yaml
from pathlib import Path
from tera.domain import TeraSchema
from tera.contracts import TeraDriver
from tera.exceptions import TeraError

class YamlFileDriver(TeraDriver):
    """
    Concrete implementation of TeraDriver.
    Reads a YAML file from disk and converts it to TeraSchema.
    """
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> TeraSchema:
        if not self.file_path.exists():
            raise FileNotFoundError(f"The file '{self.file_path}' does not exist.")

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f)

            if raw_data is None:
                raise ValueError("The YAML file is empty.")

            return TeraSchema(**raw_data)

        except yaml.YAMLError as e:
            raise TeraError("YAML Parsing Error", f"Invalid YAML syntax: {e}")
        except Exception as e:
            raise TeraError("Schema Validation Error", f"Could not load Tera Schema: {e}")