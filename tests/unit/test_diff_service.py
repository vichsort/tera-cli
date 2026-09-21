import pytest
from tera.domain import (
    TeraSchema,
    ApiConfig,
    Endpoint,
    EndpointParams,
    ParamField,
    BodyField,
    EndpointResponses,
    ResponseSuccess,
    ResponseError,
    AuthConfig
)
from tera.services import DiffService

@pytest.fixture
def base_schema() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(
            name="Test API",
            version="1.0.0",
            description="Base description",
            base_url="/v1"
        ),
        endpoints=[
            Endpoint(
                path="/users",
                method="GET",
                summary="List users",
                params=EndpointParams(
                    query=[
                        ParamField(name="limit", type="integer", required=False),
                        ParamField(name="status", type="string", required=False)
                    ]
                ),
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Users list")
                )
            ),
            Endpoint(
                path="/users/{id}",
                method="DELETE",
                summary="Delete user",
                params=EndpointParams(
                    path=[ParamField(name="id", type="string", required=True)]
                ),
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="User deleted")
                )
            ),
            Endpoint(
                path="/users",
                method="POST",
                summary="Create user",
                body=[
                    BodyField(name="username", type="string", required=True),
                    BodyField(name="email", type="string", required=False)
                ],
                responses=EndpointResponses(
                    success=ResponseSuccess(status=201, description="Created"),
                    errors=[ResponseError(status=400, message="Bad Request")]
                )
            )
        ]
    )

def test_diff_identical_schemas(base_schema: TeraSchema) -> None:
    service = DiffService()
    diff = service.compare(base_schema, base_schema)

    assert diff.is_empty is True
    assert diff.has_breaking_changes is False
    assert diff.total_changes == 0
    assert diff.breaking_count == 0

def test_diff_api_changes(base_schema: TeraSchema) -> None:
    head = base_schema.model_copy(deep=True)
    head.api.version = "1.1.0"
    head.api.base_url = "/v2"
    head.api.auth = AuthConfig(type="bearer")

    service = DiffService()
    diff = service.compare(base_schema, head)

    assert diff.is_empty is False
    assert diff.has_breaking_changes is True
    assert len(diff.api_changes) == 3

    # version is non-breaking metadata
    ver_change = next(c for c in diff.api_changes if c.path == "api.version")
    assert ver_change.category == "metadata"
    assert ver_change.impact == "non_breaking"

    # base_url is breaking structural
    url_change = next(c for c in diff.api_changes if c.path == "api.base_url")
    assert url_change.category == "structural"
    assert url_change.impact == "breaking"

    # auth added is breaking structural
    auth_change = next(c for c in diff.api_changes if c.path == "api.auth")
    assert auth_change.category == "structural"
    assert auth_change.impact == "breaking"

def test_diff_endpoint_added_and_removed(base_schema: TeraSchema) -> None:
    head = base_schema.model_copy(deep=True)
    # Remove DELETE /users/{id}
    head.endpoints = [ep for ep in head.endpoints if ep.method != "DELETE"]
    # Add GET /health
    head.endpoints.append(
        Endpoint(
            path="/health",
            method="GET",
            summary="Healthcheck",
            responses=EndpointResponses(
                success=ResponseSuccess(status=200, description="OK")
            )
        )
    )

    service = DiffService()
    diff = service.compare(base_schema, head)

    assert diff.is_empty is False
    assert diff.has_breaking_changes is True

    # 1 removed (breaking) + 1 added (non-breaking)
    removed_ep = next(ep for ep in diff.endpoint_diffs if ep.kind == "removed")
    assert removed_ep.method == "DELETE"
    assert removed_ep.path == "/users/{id}"
    assert removed_ep.impact == "breaking"

    added_ep = next(ep for ep in diff.endpoint_diffs if ep.kind == "added")
    assert added_ep.method == "GET"
    assert added_ep.path == "/health"
    assert added_ep.impact == "non_breaking"

def test_diff_endpoint_param_changes(base_schema: TeraSchema) -> None:
    head = base_schema.model_copy(deep=True)
    get_users = next(ep for ep in head.endpoints if ep.method == "GET" and ep.path == "/users")
    assert get_users.params is not None

    # status becomes required (breaking)
    status_p = next(p for p in get_users.params.query if p.name == "status")
    status_p.required = True

    # add optional filter (non-breaking)
    get_users.params.query.append(ParamField(name="search", type="string", required=False))

    # remove limit (non-breaking for optional query)
    get_users.params.query = [p for p in get_users.params.query if p.name != "limit"]

    service = DiffService()
    diff = service.compare(base_schema, head)

    assert diff.has_breaking_changes is True
    mod_ep = next(ep for ep in diff.endpoint_diffs if ep.method == "GET" and ep.path == "/users")
    assert mod_ep.impact == "breaking"

    breaking_changes = [c for c in mod_ep.changes if c.impact == "breaking"]
    assert len(breaking_changes) == 1
    assert "status" in breaking_changes[0].path

def test_diff_body_field_changes(base_schema: TeraSchema) -> None:
    head = base_schema.model_copy(deep=True)
    post_users = next(ep for ep in head.endpoints if ep.method == "POST" and ep.path == "/users")

    # Change email type string -> integer (breaking)
    email_f = next(f for f in post_users.body if f.name == "email")
    email_f.type = "integer"

    # Add optional avatar (non-breaking)
    post_users.body.append(BodyField(name="avatar", type="string", required=False))

    service = DiffService()
    diff = service.compare(base_schema, head)

    assert diff.has_breaking_changes is True
    post_diff = next(ep for ep in diff.endpoint_diffs if ep.method == "POST")
    assert post_diff.impact == "breaking"
    assert any(c.path.endswith("email].type") and c.impact == "breaking" for c in post_diff.changes)
    assert any(c.path.endswith("body[avatar]") and c.impact == "non_breaking" for c in post_diff.changes)

def test_diff_responses_and_auth(base_schema: TeraSchema) -> None:
    head = base_schema.model_copy(deep=True)
    post_users = next(ep for ep in head.endpoints if ep.method == "POST" and ep.path == "/users")

    # Change success status 201 -> 200 (breaking)
    post_users.responses.success.status = 200
    # Enable auth_required (breaking)
    post_users.auth_required = True
    # Add new error code 409 (non-breaking)
    post_users.responses.errors.append(ResponseError(status=409, message="Conflict"))

    service = DiffService()
    diff = service.compare(base_schema, head)

    assert diff.has_breaking_changes is True
    post_diff = next(ep for ep in diff.endpoint_diffs if ep.method == "POST")
    assert any(c.path.endswith("responses.success.status") and c.impact == "breaking" for c in post_diff.changes)
    assert any(c.path.endswith("auth_required") and c.impact == "breaking" for c in post_diff.changes)
    assert any(c.path.endswith("responses.errors[409]") and c.impact == "non_breaking" for c in post_diff.changes)
