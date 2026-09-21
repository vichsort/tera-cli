import json
import pytest
import yaml
from pathlib import Path
from tera.domain import (
    TeraSchema,
    Endpoint,
    ParamField,
    BodyField,
    ResponseSuccess,
    AuthConfig,
    ApiConfig,
    EndpointParams,
    EndpointResponses,
)
from tera.writers import (
    JsonFileWriter,
    YamlFileWriter,
    OpenApiJsonWriter,
    OpenApiYamlWriter,
    MarkdownWriter,
    HtmlWriter,
    PostmanWriter,
)


@pytest.fixture
def sample_schema() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(
            name="Writer Test API",
            version="1.0.0",
            description="API for testing writers",
            auth=AuthConfig(type="bearer"),
        ),
        endpoints=[
            Endpoint(
                path="/users/{id}",
                method="GET",
                summary="Get user by ID",
                description="Fetches a single user record",
                auth_required=True,
                params=EndpointParams(
                    path=[ParamField(name="id", type="integer", required=True, description="User ID")]
                ),
                responses=EndpointResponses(
                    success=ResponseSuccess(
                        status=200,
                        description="User found",
                        example={"id": 1, "name": "Alice"},
                    )
                ),
            ),
            Endpoint(
                path="/users",
                method="POST",
                summary="Create user",
                description="Creates a new user record",
                auth_required=False,
                body=[
                    BodyField(name="name", type="string", required=True, description="User name"),
                    BodyField(name="age", type="integer", required=False, description="User age"),
                ],
                responses=EndpointResponses(
                    success=ResponseSuccess(
                        status=201,
                        description="User created",
                        example={"id": 2, "name": "Bob"},
                    )
                ),
            ),
        ],
    )


def test_json_file_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "openapi.json"
    writer = JsonFileWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["openapi"] == "3.0.3"
    assert data["info"]["title"] == "Writer Test API"
    assert "/users/{id}" in data["paths"]
    assert "get" in data["paths"]["/users/{id}"]


def test_yaml_file_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "docs_out.yaml"
    writer = YamlFileWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    data = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    assert data["api"]["name"] == "Writer Test API"
    assert len(data["endpoints"]) == 2
    assert data["endpoints"][0]["path"] == "/users/{id}"


def test_openapi_json_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "spec.json"
    writer = OpenApiJsonWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["openapi"] == "3.0.3"
    assert data["info"]["version"] == "1.0.0"


def test_openapi_yaml_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "spec.yaml"
    writer = OpenApiYamlWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    data = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    assert data["openapi"] == "3.0.3"
    assert data["info"]["title"] == "Writer Test API"


def test_markdown_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "API.md"
    writer = MarkdownWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "Writer Test API" in content
    assert "/users/{id}" in content
    assert "GET" in content


def test_markdown_writer_template_not_found(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "API.md"
    writer = MarkdownWriter(output_file)
    writer.templates_dir = tmp_path / "non_existent_dir"

    with pytest.raises(FileNotFoundError, match="Template not found"):
        writer.write(sample_schema)


def test_html_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "docs.html"
    writer = HtmlWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content or "<html" in content
    assert "Writer Test API" in content
    assert "redoc" in content.lower()


def test_html_writer_template_not_found(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "docs.html"
    writer = HtmlWriter(output_file)
    writer.templates_dir = tmp_path / "non_existent_dir"

    with pytest.raises(FileNotFoundError, match="HTML Template not found"):
        writer.write(sample_schema)


def test_postman_writer(tmp_path: Path, sample_schema: TeraSchema) -> None:
    output_file = tmp_path / "collection.json"
    writer = PostmanWriter(output_file)
    writer.write(sample_schema)

    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))
    assert data["info"]["name"] == "Writer Test API"
    assert data["info"]["schema"] == "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    assert len(data["item"]) == 2

    # Check GET item
    get_item = data["item"][0]
    assert get_item["name"] == "GET /users/{id}"
    assert get_item["request"]["method"] == "GET"
    assert ":id" in get_item["request"]["url"]["raw"]

    # Check POST item with body
    post_item = data["item"][1]
    assert post_item["name"] == "POST /users"
    assert post_item["request"]["method"] == "POST"
    assert "body" in post_item["request"]
    body_data = json.loads(post_item["request"]["body"]["raw"])
    assert "name" in body_data
    assert "age" in body_data

