from pathlib import Path
import yaml
from tera.domain import TeraSchema

class YamlFileDriver:
    """
    Concrete implementation of TeraDriver.
    Reads a YAML file from disk and converts it to TeraSchema.
    """
    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> TeraSchema:
        # Validation
        if not self.file_path.exists():
            raise FileNotFoundError(f"The file '{self.file_path}' does not exist.")

        # Raw Read
        with open(self.file_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)

        if raw_data is None:
            raise ValueError("The YAML file is empty.")

        return TeraSchema(**raw_data)