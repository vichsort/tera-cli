from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from tera.core import factory
from tera.domain import TeraSchema
from tera.drivers.git_driver import GitFileDriver
from tera.drivers.yaml_driver import TeraFileDriver, YamlFileDriver
from tera.drivers.flask_driver import FlaskAppDriver
from tera.exceptions import TeraError
from tera.services.diff_loader import load_schema_from_source


def test_git_file_driver_loads_valid_yaml() -> None:
    sample_yaml = """
api:
  name: Git API
  version: 2.0.0
endpoints: []
"""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = sample_yaml
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res) as mock_run:
        driver = GitFileDriver(revision="HEAD~1", file_path="docs.yaml")
        schema = driver.load()

        mock_run.assert_called_once_with(
            ["git", "show", "HEAD~1:docs.yaml"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert isinstance(schema, TeraSchema)
        assert schema.api.name == "Git API"
        assert schema.api.version == "2.0.0"


def test_git_file_driver_loads_valid_json() -> None:
    sample_json = '{"api": {"name": "JSON API", "version": "1.1.0"}, "endpoints": []}'
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = sample_json
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res):
        driver = GitFileDriver(revision="main", file_path="docs.json")
        schema = driver.load()
        assert schema.api.name == "JSON API"
        assert schema.api.version == "1.1.0"


def test_git_file_driver_loads_openapi_from_git() -> None:
    openapi_yaml = """
openapi: 3.0.0
info:
  title: OpenAPI Git Spec
  version: 3.1.0
paths:
  /ping:
    get:
      summary: Ping
      responses:
        '200':
          description: Pong
"""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = openapi_yaml
    mock_res.stderr = ""

    with patch("subprocess.run", return_value=mock_res):
        driver = GitFileDriver(revision="v1.0.0", file_path="openapi.yaml")
        schema = driver.load()
        assert schema.api.name == "OpenAPI Git Spec"
        assert len(schema.endpoints) == 1
        assert schema.endpoints[0].path == "/ping"


def test_git_file_driver_revision_not_found() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 128
    mock_res.stdout = ""
    mock_res.stderr = "fatal: path 'docs.yaml' does not exist in 'HEAD~99'"

    with patch("subprocess.run", return_value=mock_res):
        driver = GitFileDriver(revision="HEAD~99", file_path="docs.yaml")
        with pytest.raises(TeraError) as exc_info:
            driver.load()
        assert "Git Reference Error" in str(exc_info.value)


def test_git_file_driver_git_unavailable() -> None:
    with patch("subprocess.run", side_effect=FileNotFoundError):
        driver = GitFileDriver(revision="HEAD", file_path="docs.yaml")
        with pytest.raises(TeraError) as exc_info:
            driver.load()
        assert "Git Unavailable" in str(exc_info.value)


def test_factory_get_driver_disambiguation() -> None:
    # 1. Explicit git: prefix
    d1 = factory.get_driver("git:HEAD~1:docs.yaml")
    assert isinstance(d1, GitFileDriver)
    assert d1.revision == "HEAD~1"
    assert d1.file_path == "docs.yaml"

    # 2. Colon syntax with revision pattern
    d2 = factory.get_driver("HEAD:docs.json")
    assert isinstance(d2, GitFileDriver)
    assert d2.revision == "HEAD"
    assert d2.file_path == "docs.json"

    # 3. Colon syntax with Flask app
    d3 = factory.get_driver("myapp:app")
    assert isinstance(d3, FlaskAppDriver)

    # 4. Explicit driver_type
    d4 = factory.get_driver("v1.0.0:custom.yaml", driver_type="git")
    assert isinstance(d4, GitFileDriver)

    # 5. Local file specification
    d5 = factory.get_driver("docs.yaml")
    assert isinstance(d5, YamlFileDriver)
    assert isinstance(d5, TeraFileDriver)



def test_load_schema_from_source_with_json_and_openapi(tmp_path: Path) -> None:
    # Tera JSON file
    json_file = tmp_path / "docs.json"
    json_file.write_text('{"api": {"name": "JSON Direct", "version": "1.0.0"}, "endpoints": []}', encoding="utf-8")
    s1 = load_schema_from_source(json_file)
    assert s1.api.name == "JSON Direct"

    # OpenAPI YAML file through load_schema_from_source
    openapi_file = tmp_path / "openapi.yaml"
    openapi_file.write_text("""
openapi: 3.0.0
info:
  title: Direct OpenAPI
  version: 1.0.0
paths: {}
""", encoding="utf-8")
    s2 = load_schema_from_source(openapi_file)
    assert s2.api.name == "Direct OpenAPI"
