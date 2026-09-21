from pathlib import Path
from typing import Any, Union, Literal, Optional
from tera.contracts import TeraDriver, TeraWriter
from tera.core.registry import (
    default_driver_registry,
    default_writer_registry,
    parse_git_reference,
)

DriverType = Union[Literal['tera', 'openapi', 'flask', 'git', 'fastapi', 'http', 'postman', 'har'], str]
WriterFormatStyle = Union[Literal['tera', 'openapi', 'markdown', 'html', 'postman'], str]

# Backwards compatibility alias
_parse_git_reference = parse_git_reference


def get_driver(source: Any, driver_type: Optional[DriverType] = None) -> TeraDriver:
    """
    Factory method for input drivers.
    Resolves driver through the centralized DriverRegistry.
    """
    return default_driver_registry.get(source, driver_type=driver_type)


def get_writer(output_path: Path, format_style: WriterFormatStyle = 'tera') -> TeraWriter:
    """
    Factory method for output writers.
    Resolves writer through the centralized WriterRegistry.
    """
    return default_writer_registry.get(output_path, format_style=format_style)