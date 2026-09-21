from typing import List, Any

class TeraError(Exception):
    """Base class for all Tera CLI exceptions."""
    def __init__(self, title: str, message: str):
        self.title = title
        self.message = message
        super().__init__(f"{title}: {message}")

class YamlSyntaxError(TeraError):
    """Raised when YAML syntax is invalid."""
    pass

class SchemaValidationError(TeraError):
    """Raised when data fails schema validation."""
    def __init__(self, errors: List[Any]):
        self.errors: List[Any] = errors
        super().__init__("Validation Error", "The file does not follow the expected schema.")

class FileLoadError(TeraError):
    """Raised when failing to open or read a file."""
    pass