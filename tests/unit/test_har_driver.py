import json
import pytest
from pathlib import Path
from typing import Any, Dict

from tera.core.factory import get_driver
from tera.domain.models import TeraSchema
from tera.drivers.har_driver import HarDriver
from tera.exceptions import TeraError


def _make_har(entries: list[Dict[str, Any]], creator_name: str = "TestCapture") -> Dict[str, Any]:
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": creator_name, "version": "1.0"},
            "entries": entries,
        }
    }


def test_har_driver_empty_entries() -> None:
    har_dict = _make_har([])
    driver = HarDriver(har_dict)
    schema = driver.load()

    assert isinstance(schema, TeraSchema)
    assert schema.api.name == "HAR Capture (TestCapture)"
    assert len(schema.endpoints) == 0


def test_har_driver_basic_get() -> None:
    entry: Dict[str, Any] = {
        "request": {
            "method": "GET",
            "url": "https://api.example.com/api/v1/health",
            "headers": [],
            "queryString": [],
        },
        "response": {
            "status": 200,
            "statusText": "OK",
            "headers": [],
            "content": {
                "mimeType": "application/json",
                "text": '{"status": "ok"}',
            },
        },
    }
    har_dict = _make_har([entry])
    driver = HarDriver(har_dict)
    schema = driver.load()

    assert len(schema.endpoints) == 1
    ep = schema.endpoints[0]
    assert ep.method == "GET"
    assert ep.path == "/api/v1/health"
    assert ep.tag == "health"
    assert ep.responses.success.status == 200
    assert ep.responses.success.example == {"status": "ok"}
    assert schema.api.base_url == "https://api.example.com"


def test_har_driver_route_collapse_numeric_ids() -> None:
    entries: list[Dict[str, Any]] = [
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/users/1",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/users/2",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/users/999",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
    ]
    har_dict = _make_har(entries)
    driver = HarDriver(har_dict)
    schema = driver.load()

    assert len(schema.endpoints) == 1
    ep = schema.endpoints[0]
    assert ep.method == "GET"
    assert ep.path == "/users/{user_id}"
    assert ep.params is not None
    assert len(ep.params.path) == 1
    assert ep.params.path[0].name == "user_id"
    assert ep.params.path[0].required is True


def test_har_driver_route_collapse_uuid_and_mongo_id() -> None:
    entries: list[Dict[str, Any]] = [
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/orders/88b77a05-e19c-4464-9a80-e4b2d357fbb4",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/categories/507f1f77bcf86cd799439011",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
    ]
    har_dict = _make_har(entries)
    driver = HarDriver(har_dict)
    schema = driver.load()

    assert len(schema.endpoints) == 2
    paths = {ep.path for ep in schema.endpoints}
    assert "/orders/{order_id}" in paths
    assert "/categories/{category_id}" in paths


def test_har_driver_nested_path_parameters() -> None:
    entry: Dict[str, Any] = {
        "request": {
            "method": "GET",
            "url": "https://api.example.com/users/42/orders/100",
            "headers": [],
            "queryString": [],
        },
        "response": {"status": 200, "statusText": "OK", "content": {}},
    }
    driver = HarDriver(_make_har([entry]))
    schema = driver.load()

    assert len(schema.endpoints) == 1
    ep = schema.endpoints[0]
    assert ep.path == "/users/{user_id}/orders/{order_id}"
    assert ep.params is not None
    param_names = [p.name for p in ep.params.path]
    assert param_names == ["user_id", "order_id"]


def test_har_driver_multi_entry_slug_collapse() -> None:
    entries: list[Dict[str, Any]] = [
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/posts/my-first-post",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
        {
            "request": {
                "method": "GET",
                "url": "https://api.example.com/posts/second-post",
                "headers": [],
                "queryString": [],
            },
            "response": {"status": 200, "statusText": "OK", "content": {}},
        },
    ]
    driver = HarDriver(_make_har(entries))
    schema = driver.load()

    assert len(schema.endpoints) == 1
    assert schema.endpoints[0].path == "/posts/{post_id}"


def test_har_driver_query_params() -> None:
    entry: Dict[str, Any] = {
        "request": {
            "method": "GET",
            "url": "https://api.example.com/products?sort=desc",
            "headers": [],
            "queryString": [
                {"name": "page", "value": "1"},
                {"name": "limit", "value": "25"},
            ],
        },
        "response": {"status": 200, "statusText": "OK", "content": {}},
    }
    driver = HarDriver(_make_har([entry]))
    schema = driver.load()

    ep = schema.endpoints[0]
    assert ep.params is not None
    query_names = {q.name: q.example for q in ep.params.query}
    assert "page" in query_names
    assert query_names["page"] == "1"
    assert "limit" in query_names
    assert query_names["limit"] == "25"


def test_har_driver_json_body_inference() -> None:
    entry: Dict[str, Any] = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/users",
            "headers": [{"name": "Content-Type", "value": "application/json"}],
            "postData": {
                "mimeType": "application/json",
                "text": json.dumps({
                    "username": "johndoe",
                    "age": 28,
                    "score": 95.5,
                    "is_active": True,
                    "roles": ["editor"],
                    "meta": {"verified": True},
                }),
            },
        },
        "response": {"status": 201, "statusText": "Created", "content": {}},
    }
    driver = HarDriver(_make_har([entry]))
    schema = driver.load()

    ep = schema.endpoints[0]
    assert ep.method == "POST"
    fields = {f.name: f.type for f in ep.body}
    assert fields["username"] == "string"
    assert fields["age"] == "integer"
    assert fields["score"] == "number"
    assert fields["is_active"] == "boolean"
    assert fields["roles"] == "array"
    assert fields["meta"] == "object"


def test_har_driver_form_data_body() -> None:
    entry: Dict[str, Any] = {
        "request": {
            "method": "POST",
            "url": "https://api.example.com/oauth/token",
            "headers": [],
            "postData": {
                "mimeType": "application/x-www-form-urlencoded",
                "params": [
                    {"name": "grant_type", "value": "password"},
                    {"name": "username", "value": "alice"},
                ],
            },
        },
        "response": {"status": 200, "statusText": "OK", "content": {}},
    }
    driver = HarDriver(_make_har([entry]))
    schema = driver.load()

    ep = schema.endpoints[0]
    body_names = [f.name for f in ep.body]
    assert "grant_type" in body_names
    assert "username" in body_names


def test_har_driver_responses_aggregation() -> None:
    entries: list[Dict[str, Any]] = [
        {
            "request": {"method": "GET", "url": "https://api.example.com/items/1", "headers": []},
            "response": {
                "status": 200,
                "statusText": "OK",
                "content": {"mimeType": "application/json", "text": '{"id": 1, "name": "Item 1"}'},
            },
        },
        {
            "request": {"method": "GET", "url": "https://api.example.com/items/999", "headers": []},
            "response": {
                "status": 404,
                "statusText": "Not Found",
                "content": {"mimeType": "application/json", "text": '{"error": "Not found"}'},
            },
        },
    ]
    driver = HarDriver(_make_har(entries))
    schema = driver.load()

    assert len(schema.endpoints) == 1
    ep = schema.endpoints[0]
    assert ep.responses.success.status == 200
    assert ep.responses.success.example == {"id": 1, "name": "Item 1"}
    assert len(ep.responses.errors) == 1
    assert ep.responses.errors[0].status == 404
    assert ep.responses.errors[0].example == {"error": "Not found"}


def test_har_driver_auth_detection() -> None:
    entry: Dict[str, Any] = {
        "request": {
            "method": "GET",
            "url": "https://api.example.com/secure/profile",
            "headers": [{"name": "Authorization", "value": "Bearer my-jwt-token"}],
        },
        "response": {"status": 200, "statusText": "OK", "content": {}},
    }
    driver = HarDriver(_make_har([entry]))
    schema = driver.load()

    assert schema.api.auth is not None
    assert schema.api.auth.type == "bearer"
    assert schema.endpoints[0].auth_required is True


def test_har_driver_factory_and_registry_resolution(tmp_path: Path) -> None:
    har_file = tmp_path / "traffic.har"
    har_file.write_text(json.dumps(_make_har([])), encoding="utf-8")

    # File path auto-detection by .har extension
    driver1 = get_driver(har_file)
    assert isinstance(driver1, HarDriver)

    # Dictionary auto-detection
    har_dict = _make_har([])
    driver2 = get_driver(har_dict)
    assert isinstance(driver2, HarDriver)

    # Explicit driver_type="har"
    driver3 = get_driver(har_file, driver_type="har")
    assert isinstance(driver3, HarDriver)


def test_har_driver_file_errors(tmp_path: Path) -> None:
    non_existent = tmp_path / "does_not_exist.har"
    with pytest.raises(FileNotFoundError):
        HarDriver(non_existent).load()

    invalid_json = tmp_path / "broken.har"
    invalid_json.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(TeraError):
        HarDriver(invalid_json).load()

    missing_log = tmp_path / "missing_log.har"
    missing_log.write_text('{"foo": "bar"}', encoding="utf-8")
    with pytest.raises(TeraError):
        HarDriver(missing_log).load()
