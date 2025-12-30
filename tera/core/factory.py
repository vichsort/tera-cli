from pathlib import Path
from typing import Union
from tera.contracts import TeraDriver, TeraWriter
from tera.drivers import YamlFileDriver, FlaskAppDriver
from tera.writers import JsonFileWriter, YamlFileWriter

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

def get_writer(output_path: Path) -> TeraWriter:
    """
    Factory Method for output writers.
    Decides which writer to instantiate based on the output file extension.
    """
    if output_path.suffix in ['.yaml', '.yml']:
        return YamlFileWriter(output_path)
    
    return JsonFileWriter(output_path)