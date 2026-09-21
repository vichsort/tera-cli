import sys
from pathlib import Path
from typing import Any, Dict
import pytest
from tera.core import factory
from tera.drivers import FastApiDriver
from tera.exceptions import TeraError


class MockFastApiApp:
    def __init__(self, title: str = "FastAPI Mock", version: str = "1.0.0") -> None:
        self.title = title
        self.version = version

    def openapi(self) -> Dict[str, Any]:
        return {
            "openapi": "3.1.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": "Mock FastAPI Application",
            },
            "paths": {
                "/api/v1/users": {
                    "get": {
                        "summary": "List Users",
                        "description": "Retrieve all active users",
                        "parameters": [
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Successful user list",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "post": {
                        "summary": "Create User",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "username": {"type": "string"},
                                            "email": {"type": "string"},
                                        },
                                        "required": ["username"],
                                    }
                                }
                            }
                        },
                        "responses": {
                            "201": {"description": "User created successfully"}
                        },
                    },
                }
            },
        }


def test_fastapi_driver_with_instance() -> None:
    app = MockFastApiApp(title="Order API", version="2.5.0")
    driver = FastApiDriver(app)
    schema = driver.load()

    assert schema.api.name == "Order API"
    assert schema.api.version == "2.5.0"
    assert len(schema.endpoints) == 2

    get_ep = next(ep for ep in schema.endpoints if ep.method == "GET")
    assert get_ep.path == "/api/v1/users"
    assert get_ep.summary == "List Users"
    assert get_ep.params is not None
    assert get_ep.params.query is not None
    assert len(get_ep.params.query) == 1
    assert get_ep.params.query[0].name == "limit"
    assert get_ep.params.query[0].type == "integer"

    post_ep = next(ep for ep in schema.endpoints if ep.method == "POST")
    assert post_ep.path == "/api/v1/users"
    assert post_ep.body is not None
    assert len(post_ep.body) == 2
    body_field_names = {f.name for f in post_ep.body}
    assert "username" in body_field_names
    assert "email" in body_field_names


def test_fastapi_driver_with_factory() -> None:
    def create_app() -> MockFastApiApp:
        return MockFastApiApp(title="Factory API", version="3.0.0")

    driver = FastApiDriver(create_app)
    schema = driver.load()
    assert schema.api.name == "Factory API"
    assert schema.api.version == "3.0.0"


def test_fastapi_driver_with_import_string(tmp_path: Path) -> None:
    mod_file = tmp_path / "mock_app_module.py"
    mod_file.write_text(
        "from tests.unit.test_fastapi_driver import MockFastApiApp\n"
        "app = MockFastApiApp(title='Imported FastAPI', version='1.1.0')\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        driver = FastApiDriver("mock_app_module:app")
        schema = driver.load()
        assert schema.api.name == "Imported FastAPI"
        assert schema.api.version == "1.1.0"
    finally:
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))


def test_fastapi_auto_detection_in_registry(tmp_path: Path) -> None:
    mod_file = tmp_path / "auto_detect_fastapi.py"
    mod_file.write_text(
        "from tests.unit.test_fastapi_driver import MockFastApiApp\n"
        "app = MockFastApiApp(title='Auto Detected App', version='1.0.0')\n",
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        driver = factory.get_driver("auto_detect_fastapi:app")
        assert isinstance(driver, FastApiDriver)
        schema = driver.load()
        assert schema.api.name == "Auto Detected App"
    finally:
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))


def test_fastapi_explicit_driver_type() -> None:
    app = MockFastApiApp(title="Explicit Type App")
    driver = factory.get_driver(app, driver_type="fastapi")
    assert isinstance(driver, FastApiDriver)
    schema = driver.load()
    assert schema.api.name == "Explicit Type App"


def test_fastapi_driver_invalid_app_missing_openapi() -> None:
    class NotFastAPI:
        pass

    driver = FastApiDriver(NotFastAPI())
    with pytest.raises(TeraError) as exc:
        driver.load()
    assert "Invalid FastAPI App" in str(exc.value)


def test_fastapi_driver_openapi_not_returning_dict() -> None:
    class BadApp:
        def openapi(self) -> Any:
            return "not-a-dict"

    driver = FastApiDriver(BadApp())
    with pytest.raises(TeraError) as exc:
        driver.load()
    assert "Invalid OpenAPI Schema" in str(exc.value)


def test_fastapi_driver_openapi_raises_exception() -> None:
    class FailingApp:
        def openapi(self) -> Any:
            raise RuntimeError("Internal crash")

    driver = FastApiDriver(FailingApp())
    with pytest.raises(TeraError) as exc:
        driver.load()
    assert "OpenAPI Generation Error" in str(exc.value)


def test_fastapi_driver_import_error() -> None:
    driver = FastApiDriver("non_existent_module_xyz:app")
    with pytest.raises(TeraError) as exc:
        driver.load()
    assert "FastAPI Load Error" in str(exc.value)


def test_fastapi_driver_factory_error() -> None:
    def broken_factory() -> Any:
        raise ValueError("Cannot initialize")

    driver = FastApiDriver(broken_factory)
    with pytest.raises(TeraError) as exc:
        driver.load()
    assert "FastAPI Factory Error" in str(exc.value)
