from pathlib import Path
from typing import Union
from tera.core import factory
from tera.domain import TeraSchema
from tera.exceptions import TeraError


def load_schema_from_source(source: Union[str, Path]) -> TeraSchema:
    """
    Loads a TeraSchema instance from either a local file, git revision reference, or application.
    Delegates to the driver factory architecture.

    Supported formats:
      - Local paths: 'docs.yaml', 'docs.v1.json', Path('docs.yaml')
      - Git revisions: 'git:HEAD~1:docs.yaml', 'HEAD~1:docs.yaml', 'HEAD:docs.yaml'
      - OpenAPI specs: 'openapi.yaml', 'swagger.json'
    """
    try:
        driver = factory.get_driver(source)
        return driver.load()
    except (FileNotFoundError, TeraError):
        raise
    except Exception as e:
        raise TeraError("Schema Load Error", f"Failed to load schema from '{source}': {str(e)}")

