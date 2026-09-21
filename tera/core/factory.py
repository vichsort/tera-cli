from pathlib import Path
from typing import Union, Literal, Optional
from tera.contracts import TeraDriver, TeraWriter
from tera.drivers import YamlFileDriver, FlaskAppDriver, OpenApiDriver
from tera.writers import (
    JsonFileWriter, 
    YamlFileWriter, 
    OpenApiJsonWriter, 
    OpenApiYamlWriter,
    MarkdownWriter,
    HtmlWriter,
    PostmanWriter
)

DriverType = Literal['tera', 'openapi', 'flask']

def get_driver(source: Union[str, Path], driver_type: Optional[DriverType] = None) -> TeraDriver:
    """
    Factory Method for input drivers.
    Decides which driver to instantiate based on input format or explicit driver_type.
    """
    if driver_type == 'openapi':
        return OpenApiDriver(Path(source))
    if driver_type == 'flask':
        return FlaskAppDriver(str(source))
    if driver_type == 'tera':
        return YamlFileDriver(Path(source))

    source_str = str(source)
    if ":" in source_str and not Path(source_str).exists():
        return FlaskAppDriver(source_str)

    path = Path(source_str)
    if path.exists() and path.suffix.lower() in ('.json', '.yaml', '.yml'):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                header = f.read(512)
                if (
                    '"openapi"' in header or "'openapi'" in header or 'openapi:' in header or
                    '"swagger"' in header or "'swagger'" in header or 'swagger:' in header
                ):
                    return OpenApiDriver(path)
        except Exception:
            pass
        return YamlFileDriver(path)

    if source_str.endswith(('.yaml', '.yml')):
        return YamlFileDriver(Path(source_str))

    raise ValueError(
        f"Could not determine driver for input: '{source}'. "
        "Supported formats: .yaml/.json files or 'module:app' strings."
    )

WriterFormatStyle = Literal['tera', 'openapi', 'markdown', 'html', 'postman']

def get_writer(output_path: Path, format_style: WriterFormatStyle = 'tera') -> TeraWriter:
    """
    Factory Method for output writers.
    Decides based on file extension AND the desired format style.
    
    Args:
        output_path: Destination path.
        format_style: 'tera' (Canonical YAML/JSON), 'openapi', 'markdown', 'html', or 'postman'.
    """
    is_yaml = output_path.suffix in ['.yaml', '.yml']
    
    if format_style == 'tera':
        if is_yaml:
            return YamlFileWriter(output_path)
        return JsonFileWriter(output_path)
    
    if format_style == 'openapi':
        if is_yaml:
            return OpenApiYamlWriter(output_path)
        return OpenApiJsonWriter(output_path)
    
    if format_style == 'markdown':
        return MarkdownWriter(output_path)
    
    if format_style == 'html':
        return HtmlWriter(output_path)
    
    if format_style == 'postman':
        return PostmanWriter(output_path)
        
    raise ValueError(f"Unknown format style: {format_style}")