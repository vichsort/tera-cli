from pathlib import Path
from typing import Union, Literal
from tera.contracts import TeraDriver, TeraWriter
from tera.drivers import YamlFileDriver, FlaskAppDriver
from tera.writers import (
    JsonFileWriter, 
    YamlFileWriter, 
    OpenApiJsonWriter, 
    OpenApiYamlWriter,
    MarkdownWriter,
    HtmlWriter,
    PostmanWriter
)

def get_driver(source: Union[str, Path]) -> TeraDriver:
    """
    Factory Method for input drivers.
    Decides which driver to instantiate based on the input string format.
    """
    source_str = str(source)
    
    if source_str.endswith(('.yaml', '.yml')):
        return YamlFileDriver(Path(source_str))

    if ":" in source_str:
        return FlaskAppDriver(source_str)
        
    raise ValueError(
        f"Could not determine driver for input: '{source}'. "
        "Supported formats: .yaml files or 'module:app' strings."
    )

def get_writer(output_path: Path, format_style: Literal['tera', 'openapi'] = 'tera') -> TeraWriter:
    """
    Factory Method for output writers.
    Decides based on file extension AND the desired format style.
    
    Args:
        output_path: Destination path.
        format_style: 'tera' (Canonical YAML/JSON) or 'openapi' (Export format).
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