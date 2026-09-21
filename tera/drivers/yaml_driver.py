from pathlib import Path
from typing import Union

from tera.contracts import TeraDriver
from tera.domain import TeraSchema, LintSeverity
from tera.adapters import FileLoader
from tera.exceptions import TeraError


class YamlFileDriver(TeraDriver):
    """
    Concrete implementation of TeraDriver for canonical Tera specification files (YAML or JSON).
    """

    def __init__(self, file_path: Union[Path, str]) -> None:
        self.file_path = Path(file_path)

    def load(self) -> TeraSchema:
        if not self.file_path.exists():
            raise FileNotFoundError(f"The file '{self.file_path}' does not exist.")

        data, issues = FileLoader.load(self.file_path)
        for issue in issues:
            if issue.severity == LintSeverity.ERROR:
                raise TeraError("Schema Load Error", f"Error loading '{self.file_path}': {issue.message}")

        if data is None:
            raise TeraError("Schema Load Error", f"The file '{self.file_path}' is empty or invalid.")

        try:
            return TeraSchema.model_validate(data)
        except Exception as e:
            raise TeraError("Schema Validation Error", f"Could not load Tera Schema: {e}")


TeraFileDriver = YamlFileDriver