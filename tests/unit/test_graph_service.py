from tera.domain.models import (
    ApiConfig,
    Endpoint,
    EndpointResponses,
    ResponseSuccess,
    TeraSchema,
)
from tera.services.graph import GraphService


def create_mock_schema() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="Social API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/users",
                method="POST",
                summary="Create user",
                tag="Users",
                responses=EndpointResponses(success=ResponseSuccess(status=201)),
            ),
            Endpoint(
                path="/users",
                method="GET",
                summary="List users",
                tag="Users",
                responses=EndpointResponses(success=ResponseSuccess(status=200)),
            ),
            Endpoint(
                path="/users/{id}",
                method="GET",
                summary="Get user details",
                tag="Users",
                responses=EndpointResponses(success=ResponseSuccess(status=200)),
            ),
            Endpoint(
                path="/users/{id}",
                method="DELETE",
                summary="Delete user",
                tag="Users",
                responses=EndpointResponses(success=ResponseSuccess(status=204)),
            ),
            Endpoint(
                path="/users/{id}/posts",
                method="GET",
                summary="List user posts",
                tag="Posts",
                responses=EndpointResponses(success=ResponseSuccess(status=200)),
            ),
        ],
    )


def test_graph_service_builds_nodes_and_edges() -> None:
    schema = create_mock_schema()
    service = GraphService()
    graph = service.build_graph(schema)

    assert len(graph.nodes) == 5
    assert len(graph.edges) >= 2

    # Verify CRUD edge POST /users -> GET /users/{id}
    crud_edges = [e for e in graph.edges if e.source == "POST_/users" and "creates {id}" in (e.label or "")]
    assert len(crud_edges) >= 2  # GET /users/{id} and DELETE /users/{id}

    # Verify subresource edge
    sub_edges = [e for e in graph.edges if "/posts" in (e.label or "")]
    assert len(sub_edges) >= 1


def test_graph_to_mermaid() -> None:
    schema = create_mock_schema()
    service = GraphService()
    graph = service.build_graph(schema)

    mermaid_td = graph.to_mermaid(direction="TD")
    assert mermaid_td.startswith("flowchart TD")
    assert 'subgraph sg_Users ["Users"]' in mermaid_td
    assert "POST__users" in mermaid_td
    assert "-->" in mermaid_td

    mermaid_lr = graph.to_mermaid(direction="LR")
    assert mermaid_lr.startswith("flowchart LR")
