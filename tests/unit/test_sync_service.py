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
    ResponseError
)
from tera.services import SyncService

@pytest.fixture
def doc_spec() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="Store API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/products",
                method="GET",
                summary="List all products (Human summary)",
                description="Detailed human description",
                tag="Catalog",
                params=EndpointParams(
                    query=[ParamField(name="limit", type="integer", description="Max items to return", example=10)]
                ),
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Product catalog", example=[{"id": 1}]),
                    errors=[ResponseError(status=404, message="Not Found", description="Catalog not found")]
                )
            ),
            Endpoint(
                path="/legacy",
                method="GET",
                summary="Legacy endpoint removed from code",
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Legacy")
                )
            )
        ]
    )

@pytest.fixture
def code_spec() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="Flask App", version="1.0.0"),
        endpoints=[
            # Updated /products in code: limit is now required, added search param, new body field
            Endpoint(
                path="/products",
                method="GET",
                summary="",  # Empty in AST docstring
                auth_required=True,
                params=EndpointParams(
                    query=[
                        ParamField(name="limit", type="integer", required=True),
                        ParamField(name="search", type="string", required=False)
                    ]
                ),
                body=[BodyField(name="filter_obj", type="object", required=False)],
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Success")
                )
            ),
            # Newly created /orders in code
            Endpoint(
                path="/orders",
                method="POST",
                summary="Create order",
                responses=EndpointResponses(
                    success=ResponseSuccess(status=201, description="Created")
                )
            )
        ]
    )

def test_sync_preserves_human_metadata(doc_spec: TeraSchema, code_spec: TeraSchema) -> None:
    service = SyncService()
    result = service.sync(code_spec, doc_spec, prune=False)

    assert "/orders" in result.endpoints_added[0]
    assert "/products" in result.endpoints_updated[0]
    assert "/legacy" in result.endpoints_orphaned[0]
    assert result.annotations_preserved > 0

    merged_ep = next(ep for ep in result.merged_schema.endpoints if ep.path == "/products")
    # Human summary and description preserved!
    assert merged_ep.summary == "List all products (Human summary)"
    assert merged_ep.description == "Detailed human description"
    assert merged_ep.tag == "Catalog"

    # Code structural updates applied!
    assert merged_ep.auth_required is True
    assert merged_ep.params is not None
    limit_param = next(p for p in merged_ep.params.query if p.name == "limit")
    assert limit_param.required is True
    # Human description and example on param preserved!
    assert limit_param.description == "Max items to return"
    assert limit_param.example == 10

    # Error response preserved!
    assert len(merged_ep.responses.errors) == 1
    assert merged_ep.responses.errors[0].status == 404

def test_sync_prune_orphaned_endpoints(doc_spec: TeraSchema, code_spec: TeraSchema) -> None:
    service = SyncService()
    result = service.sync(code_spec, doc_spec, prune=True)

    assert any("/legacy" in ep for ep in result.endpoints_pruned)
    assert not any(ep.path == "/legacy" for ep in result.merged_schema.endpoints)
