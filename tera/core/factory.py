from pathlib import Path
from typing import Union, Literal, Optional, Tuple
from tera.contracts import TeraDriver, TeraWriter
from tera.drivers import YamlFileDriver, FlaskAppDriver, OpenApiDriver, GitFileDriver
from tera.writers import (
    JsonFileWriter, 
    YamlFileWriter, 
    OpenApiJsonWriter, 
    OpenApiYamlWriter,
    MarkdownWriter,
    HtmlWriter,
    PostmanWriter
)

DriverType = Literal['tera', 'openapi', 'flask', 'git']


def _parse_git_reference(source_str: str) -> Tuple[str, str]:
    git_target = source_str[4:] if source_str.startswith("git:") else source_str
    if ":" in git_target:
        parts = git_target.split(":", 1)
        return parts[0], parts[1] if parts[1] else "docs.yaml"
    return git_target, "docs.yaml"


def get_driver(source: Union[str, Path], driver_type: Optional[DriverType] = None) -> TeraDriver:
    """
    Factory Method for input drivers.
    Decides which driver to instantiate based on input format or explicit driver_type.
    """
    source_str = str(source)

    if driver_type == 'openapi':
        return OpenApiDriver(Path(source_str))
    if driver_type == 'flask':
        return FlaskAppDriver(source_str)
    if driver_type == 'tera':
        return YamlFileDriver(Path(source_str))
    if driver_type == 'git':
        rev, file_path = _parse_git_reference(source_str)
        return GitFileDriver(rev, file_path)

    # Auto-detection:
    # 1. Explicit git: prefix
    if source_str.startswith("git:"):
        rev, file_path = _parse_git_reference(source_str)
        return GitFileDriver(rev, file_path)

    # 2. Existing local file
    local_path = Path(source_str)
    if local_path.exists() and local_path.is_file():
        if local_path.suffix.lower() in ('.json', '.yaml', '.yml'):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    header = f.read(512)
                    if (
                        '"openapi"' in header or "'openapi'" in header or 'openapi:' in header or
                        '"swagger"' in header or "'swagger'" in header or 'swagger:' in header
                    ):
                        return OpenApiDriver(local_path)
            except Exception:
                pass
            return YamlFileDriver(local_path)

    # 3. Colon syntax when file doesn't exist locally: Git vs Flask app
    if ":" in source_str:
        left, right = source_str.split(":", 1)
        if (
            right.endswith(('.yaml', '.yml', '.json'))
            or left.startswith("HEAD")
            or "~" in left
            or "^" in left
            or "/" in right
        ):
            rev, file_path = _parse_git_reference(source_str)
            return GitFileDriver(rev, file_path)
        return FlaskAppDriver(source_str)

    # 4. Specification file path (yaml or json)
    if source_str.endswith(('.yaml', '.yml', '.json')):
        return YamlFileDriver(Path(source_str))

    raise ValueError(
        f"Could not determine driver for input: '{source}'. "
        "Supported formats: .yaml/.json files, 'git:rev:path' references, or 'module:app' strings."
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