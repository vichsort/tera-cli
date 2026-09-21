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
from tera.services import CoverageService

def test_coverage_fully_documented() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Full API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/items",
                method="GET",
                summary="List all items",
                description="Returns items from the catalog",
                params=EndpointParams(
                    query=[ParamField(name="limit", type="integer", description="Limit count", example=10)]
                ),
                body=[BodyField(name="filter", type="string", description="Filter string", example="shoes")],
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="OK"),
                    errors=[ResponseError(status=400, message="Bad Request")]
                )
            )
        ]
    )

    service = CoverageService()
    report = service.calculate_coverage(schema)

    assert report.total_endpoints == 1
    assert report.overall_score == 100.0
    assert report.summaries_score == 100.0
    assert report.descriptions_score == 100.0
    assert report.params_score == 100.0
    assert report.body_score == 100.0
    assert report.errors_score == 100.0
    assert len(report.endpoints[0].missing_items) == 0

def test_coverage_partially_documented() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Partial API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/items",
                method="POST",
                summary="",  # Missing summary (0/20)
                description=None,  # Missing description (0/20)
                params=EndpointParams(
                    query=[ParamField(name="code", type="string")]  # Missing param description (0/20)
                ),
                body=[],  # No body (20/20)
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="OK"),
                    errors=[]  # Missing error responses (0/20)
                )
            )
        ]
    )

    service = CoverageService()
    report = service.calculate_coverage(schema)

    assert report.total_endpoints == 1
    assert report.overall_score == 20.0
    assert len(report.endpoints[0].missing_items) == 4
    assert any("Missing summary" in item for item in report.endpoints[0].missing_items)
    assert any("Missing description" in item for item in report.endpoints[0].missing_items)
    assert any("parameter(s) missing description" in item for item in report.endpoints[0].missing_items)
    assert any("No error responses" in item for item in report.endpoints[0].missing_items)

def test_coverage_empty_schema() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Empty API", version="1.0.0"),
        endpoints=[]
    )
    service = CoverageService()
    report = service.calculate_coverage(schema)

    assert report.total_endpoints == 0
    assert report.overall_score == 100.0
