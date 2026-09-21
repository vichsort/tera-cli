import json
from pathlib import Path
from typing import Any, Dict
import pytest
from tera.core import factory
from tera.drivers import PostmanCollectionDriver
from tera.exceptions import TeraError


def test_postman_driver_v1_legacy() -> None:
    v1_data = {
        "id": "c1-uuid",
        "name": "Legacy V1 API",
        "description": "Postman v1 collection",
        "order": ["req-1"],
        "folders": [
            {
                "id": "f1-uuid",
                "name": "Users Folder",
                "description": "Folder for users",
                "order": ["req-1"],
            }
        ],
        "requests": [
            {
                "id": "req-1",
                "name": "Get User Details",
                "description": "Fetches a specific user",
                "url": "http://localhost:5000/api/users/:user_id?active=true",
                "method": "GET",
                "headers": "Authorization: Bearer my-secret-token\nContent-Type: application/json",
                "dataMode": "raw",
                "rawModeData": '{"note": "test"}',
                "responses": [
                    {
                        "responseCode": {"code": 200, "name": "OK"},
                        "text": '{"id": 123, "name": "Alice"}',
                    }
                ],
            }
        ],
    }

    driver = PostmanCollectionDriver(v1_data)
    schema = driver.load()

    assert schema.api.name == "Legacy V1 API"
    assert schema.api.version == "1.0.0"
    assert len(schema.endpoints) == 1

    ep = schema.endpoints[0]
    assert ep.path == "/api/users/{user_id}"
    assert ep.method == "GET"
    assert ep.summary == "Get User Details"
    assert ep.tag == "Users Folder"
    assert ep.auth_required is True

    assert ep.params is not None
    assert len(ep.params.path) == 1
    assert ep.params.path[0].name == "user_id"
    assert len(ep.params.query) == 1
    assert ep.params.query[0].name == "active"

    assert len(ep.body) == 1
    assert ep.body[0].name == "note"
    assert ep.body[0].type == "string"

    assert ep.responses.success.status == 200
    assert ep.responses.success.example == {"id": 123, "name": "Alice"}


def test_postman_driver_v2_0() -> None:
    v2_0_data = {
        "info": {
            "_postman_id": "v20-id",
            "name": "V2.0 API Spec",
            "description": "Postman 2.0 collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.0.0/collection.json",
        },
        "item": [
            {
                "name": "Accounts",
                "item": [
                    {
                        "name": "Fetch Account",
                        "request": {
                            "method": "GET",
                            "url": "https://api.domain.com/v1/accounts/:acc_id",
                            "description": "Fetch account info",
                            "header": [{"key": "X-Trace", "value": "123"}],
                        },
                    }
                ],
            }
        ],
    }

    driver = PostmanCollectionDriver(v2_0_data)
    schema = driver.load()

    assert schema.api.name == "V2.0 API Spec"
    assert len(schema.endpoints) == 1
    ep = schema.endpoints[0]
    assert ep.path == "/v1/accounts/{acc_id}"
    assert ep.tag == "Accounts"
    assert ep.params is not None
    assert len(ep.params.path) == 1
    assert ep.params.path[0].name == "acc_id"


def test_postman_driver_v2_1_full() -> None:
    v2_1_data: Dict[str, Any] = {
        "info": {
            "name": "Billing API v2.1",
            "description": "Complete 2.1 collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "topsecret"}],
        },
        "item": [
            {
                "name": "Invoices",
                "item": [
                    {
                        "name": "Create Invoice",
                        "request": {
                            "method": "POST",
                            "url": {
                                "raw": "{{base_url}}/api/invoices/:client_id?notify=true",
                                "path": ["api", "invoices", ":client_id"],
                                "query": [
                                    {"key": "notify", "value": "true", "description": "Notify customer"}
                                ],
                                "variable": [
                                    {"key": "client_id", "value": "42", "description": "Customer ID"}
                                ],
                            },
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(
                                    {
                                        "amount": 150.75,
                                        "items_count": 3,
                                        "paid": False,
                                        "metadata": {"source": "web"},
                                        "tags": ["urgent", "monthly"],
                                    }
                                ),
                            },
                        },
                        "response": [
                            {
                                "code": 201,
                                "status": "Created",
                                "body": '{"invoice_id": "inv_999", "status": "pending"}',
                            },
                            {
                                "code": 400,
                                "status": "Bad Request",
                                "body": '{"error": "Invalid client"}',
                            },
                        ],
                    }
                ],
            }
        ],
    }

    driver = PostmanCollectionDriver(v2_1_data)
    schema = driver.load()

    assert schema.api.name == "Billing API v2.1"
    assert schema.api.auth is not None
    assert schema.api.auth.type == "bearer"
    assert len(schema.endpoints) == 1

    ep = schema.endpoints[0]
    assert ep.path == "/api/invoices/{client_id}"
    assert ep.method == "POST"
    assert ep.summary == "Create Invoice"
    assert ep.tag == "Invoices"
    assert ep.auth_required is True

    # Check path & query params
    assert ep.params is not None
    assert len(ep.params.path) == 1
    assert ep.params.path[0].name == "client_id"
    assert len(ep.params.query) == 1
    assert ep.params.query[0].name == "notify"

    # Check body fields
    body_map = {b.name: b for b in ep.body}
    assert body_map["amount"].type == "number"
    assert body_map["items_count"].type == "integer"
    assert body_map["paid"].type == "boolean"
    assert body_map["metadata"].type == "object"
    assert body_map["tags"].type == "array"

    # Check responses
    assert ep.responses.success.status == 201
    assert ep.responses.success.description == "Created"
    assert ep.responses.success.example == {"invoice_id": "inv_999", "status": "pending"}
    assert len(ep.responses.errors) == 1
    assert ep.responses.errors[0].status == 400
    assert ep.responses.errors[0].message == "Bad Request"


def test_postman_driver_v3_draft07() -> None:
    v3_data = {
        "info": {
            "name": "Cloud API v3",
            "schema": "https://schema.postman.com/json/draft-07/collection/v3.0.0/collection.json",
        },
        "item": [
            {
                "name": "Health",
                "request": {
                    "method": "GET",
                    "url": "http://localhost/health",
                },
            }
        ],
    }

    driver = PostmanCollectionDriver(v3_data)
    schema = driver.load()

    assert schema.api.name == "Cloud API v3"
    assert len(schema.endpoints) == 1
    assert schema.endpoints[0].path == "/health"
    assert schema.endpoints[0].method == "GET"


def test_postman_driver_formdata_body() -> None:
    collection_data = {
        "info": {
            "name": "Upload API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [
            {
                "name": "Upload Avatar",
                "request": {
                    "method": "POST",
                    "url": "http://localhost/avatar",
                    "body": {
                        "mode": "formdata",
                        "formdata": [
                            {"key": "avatar_file", "type": "file", "description": "User image"},
                            {"key": "title", "value": "Profile photo", "disabled": False},
                        ],
                    },
                },
            }
        ],
    }

    driver = PostmanCollectionDriver(collection_data)
    schema = driver.load()

    assert len(schema.endpoints) == 1
    ep = schema.endpoints[0]
    assert len(ep.body) == 2
    body_map = {b.name: b for b in ep.body}
    assert "avatar_file" in body_map
    assert "title" in body_map
    assert body_map["title"].example == "Profile photo"


def test_postman_driver_file_loading_and_auto_detection(tmp_path: Path) -> None:
    collection_file = tmp_path / "sample_collection.json"
    collection_content = {
        "info": {
            "name": "Disk API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [
            {
                "name": "Ping",
                "request": "http://localhost/ping",
            }
        ],
    }
    collection_file.write_text(json.dumps(collection_content), encoding="utf-8")

    # 1. Direct driver instantiation with file path
    driver1 = PostmanCollectionDriver(collection_file)
    schema1 = driver1.load()
    assert schema1.api.name == "Disk API"

    # 2. Auto-detection via factory.get_driver
    driver2 = factory.get_driver(collection_file)
    assert isinstance(driver2, PostmanCollectionDriver)
    schema2 = driver2.load()
    assert schema2.api.name == "Disk API"


def test_postman_driver_error_handling(tmp_path: Path) -> None:
    # 1. Non-existent file
    driver1 = PostmanCollectionDriver(tmp_path / "not_found.json")
    with pytest.raises(FileNotFoundError):
        driver1.load()

    # 2. Invalid JSON file
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ unclosed", encoding="utf-8")
    driver2 = PostmanCollectionDriver(bad_json)
    with pytest.raises(TeraError) as exc2:
        driver2.load()
    assert "Postman JSON Error" in str(exc2.value)

    # 3. JSON root not a dict
    bad_root = tmp_path / "bad_root.json"
    bad_root.write_text('["not", "a", "dict"]', encoding="utf-8")
    driver3 = PostmanCollectionDriver(bad_root)
    with pytest.raises(TeraError) as exc3:
        driver3.load()
    assert "Root must be a JSON object" in str(exc3.value)

