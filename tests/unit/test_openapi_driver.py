from pathlib import Path
from typing import Any, Dict
import json
import pytest
import yaml

from tera.drivers.openapi_driver import OpenApiDriver
from tera.domain.models import TeraSchema
from tera.exceptions import TeraError


def test_openapi_driver_parses_openapi3_dict() -> None:
    spec: Dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": "Store API",
            "version": "2.1.0",
            "description": "Online store management",
        },
        "servers": [{"url": "/api/v2"}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
            "schemas": {
                "Item": {
                    "type": "object",
                    "required": ["name", "price"],
                    "properties": {
                        "name": {"type": "string", "description": "Item name"},
                        "price": {"type": "number", "description": "Price in USD"},
                    },
                }
            },
        },
        "paths": {
            "/items": {
                "get": {
                    "summary": "List all items",
                    "tags": ["Items"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "X-Trace-Id",
                            "in": "header",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "List of items",
                            "content": {
                                "application/json": {
                                    "example": [{"name": "Book", "price": 12.5}]
                                }
                            },
                        },
                        "500": {
                            "description": "Internal server error",
                        },
                    },
                },
                "post": {
                    "summary": "Create an item",
                    "tags": ["Items"],
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Item"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Item created",
                        },
                        "400": {
                            "description": "Validation error",
                        },
                    },
                },
            },
            "/items/{id}": {
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "get": {
                    "summary": "Get item by ID",
                    "responses": {
                        "200": {"description": "Item details"},
                    },
                },
            },
        },
    }

    driver = OpenApiDriver(spec)
    schema = driver.load()

    assert isinstance(schema, TeraSchema)
    assert schema.api.name == "Store API"
    assert schema.api.version == "2.1.0"
    assert schema.api.base_url == "/api/v2"
    assert schema.api.auth is not None
    assert schema.api.auth.type == "bearer"
    assert len(schema.endpoints) == 3

    # Check GET /items
    get_items = next(e for e in schema.endpoints if e.path == "/items" and e.method == "GET")
    assert get_items.summary == "List all items"
    assert get_items.tag == "Items"
    assert get_items.auth_required is False
    assert get_items.params is not None
    assert len(get_items.params.query) == 1
    assert get_items.params.query[0].name == "limit"
    assert get_items.params.query[0].type == "integer"
    assert len(get_items.params.header) == 1
    assert get_items.params.header[0].name == "X-Trace-Id"
    assert get_items.responses.success.status == 200
    assert len(get_items.responses.errors) == 1
    assert get_items.responses.errors[0].status == 500

    # Check POST /items
    post_item = next(e for e in schema.endpoints if e.path == "/items" and e.method == "POST")
    assert post_item.auth_required is True
    assert len(post_item.body) == 2
    body_names = {b.name for b in post_item.body}
    assert body_names == {"name", "price"}
    price_field = next(b for b in post_item.body if b.name == "price")
    assert price_field.type == "number"
    assert price_field.required is True
    assert post_item.responses.success.status == 201

    # Check GET /items/{id} path parameter inheritance
    get_item = next(e for e in schema.endpoints if e.path == "/items/{id}" and e.method == "GET")
    assert get_item.params is not None
    assert len(get_item.params.path) == 1
    assert get_item.params.path[0].name == "id"
    assert get_item.params.path[0].required is True


def test_openapi_driver_parses_swagger2(tmp_path: Path) -> None:
    swagger_spec: Dict[str, Any] = {
        "swagger": "2.0",
        "info": {
            "title": "Legacy Swagger API",
            "version": "1.0.0",
        },
        "host": "api.legacy.com",
        "basePath": "/v1",
        "securityDefinitions": {
            "basicAuth": {"type": "basic"}
        },
        "security": [{"basicAuth": []}],
        "paths": {
            "/users": {
                "post": {
                    "summary": "Create user",
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "required": True,
                            "schema": {
                                "type": "object",
                                "required": ["username"],
                                "properties": {
                                    "username": {"type": "string"},
                                    "is_active": {"type": "boolean"},
                                },
                            },
                        }
                    ],
                    "responses": {
                        "200": {"description": "User created"},
                    },
                }
            }
        },
    }

    yaml_file = tmp_path / "swagger.yaml"
    yaml_file.write_text(yaml.dump(swagger_spec), encoding="utf-8")

    driver = OpenApiDriver(yaml_file)
    schema = driver.load()

    assert schema.api.name == "Legacy Swagger API"
    assert schema.api.base_url == "/v1"
    assert schema.api.auth is not None
    assert schema.api.auth.type == "basic"
    assert len(schema.endpoints) == 1

    ep = schema.endpoints[0]
    assert ep.path == "/users"
    assert ep.method == "POST"
    assert ep.auth_required is True  # From global security
    assert len(ep.body) == 2
    user_field = next(b for b in ep.body if b.name == "username")
    assert user_field.type == "string"
    assert user_field.required is True
    active_field = next(b for b in ep.body if b.name == "is_active")
    assert active_field.type == "boolean"


def test_openapi_driver_file_json(tmp_path: Path) -> None:
    spec: Dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": "JSON API", "version": "0.1.0"},
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health check",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    json_file = tmp_path / "openapi.json"
    json_file.write_text(json.dumps(spec), encoding="utf-8")

    driver = OpenApiDriver(json_file)
    schema = driver.load()

    assert schema.api.name == "JSON API"
    assert len(schema.endpoints) == 1
    assert schema.endpoints[0].path == "/health"


def test_openapi_driver_file_not_found() -> None:
    driver = OpenApiDriver(Path("/non/existent/path/spec.json"))
    with pytest.raises(FileNotFoundError):
        driver.load()


def test_openapi_driver_invalid_syntax(tmp_path: Path) -> None:
    bad_file = tmp_path / "invalid.yaml"
    bad_file.write_text("openapi: 3.0.0\n  bad: [unclosed", encoding="utf-8")

    driver = OpenApiDriver(bad_file)
    with pytest.raises(TeraError):
        driver.load()
