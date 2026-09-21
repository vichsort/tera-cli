from tera.domain import (
    TeraSchema,
    ApiConfig,
    Endpoint,
    EndpointParams,
    ParamField,
    EndpointResponses,
    ResponseSuccess,
)


def test_endpoint_params_all_params() -> None:
    params = EndpointParams(
        query=[ParamField(name="q", type="string")],
        path=[ParamField(name="id", type="integer")],
        header=[ParamField(name="X-Trace", type="string")],
    )
    all_p = params.all_params
    assert len(all_p) == 3
    assert [p.name for p in all_p] == ["q", "id", "X-Trace"]


def test_endpoint_properties_and_normalization() -> None:
    ep = Endpoint(
        path="/items/{id}",
        method="get",  # type: ignore (testing validator)
        summary="Get item",
        responses=EndpointResponses(
            success=ResponseSuccess(status=200, description="OK")
        ),
    )
    assert ep.method == "GET"
    assert ep.key == ("GET", "/items/{id}")
    assert ep.identifier == "GET /items/{id}"


def test_schema_endpoint_map_and_get_endpoint() -> None:
    ep1 = Endpoint(
        path="/users",
        method="POST",
        summary="Create user",
        responses=EndpointResponses(
            success=ResponseSuccess(status=201, description="Created")
        ),
    )
    ep2 = Endpoint(
        path="/users/{id}",
        method="GET",
        summary="Get user",
        responses=EndpointResponses(
            success=ResponseSuccess(status=200, description="OK")
        ),
    )
    schema = TeraSchema(
        api=ApiConfig(name="Test API", version="1.0.0"),
        endpoints=[ep1, ep2],
    )

    mapping = schema.endpoint_map
    assert len(mapping) == 2
    assert mapping[("POST", "/users")] == ep1
    assert mapping[("GET", "/users/{id}")] == ep2

    # Lookup case-insensitive method
    assert schema.get_endpoint("post", "/users") == ep1
    assert schema.get_endpoint("GET", "/users/{id}") == ep2
    assert schema.get_endpoint("DELETE", "/users") is None
