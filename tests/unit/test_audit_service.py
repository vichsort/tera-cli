from tera.domain.models import (
    ApiConfig,
    Endpoint,
    EndpointResponses,
    ResponseSuccess,
    TeraSchema,
)
from tera.services.audit import AuditService


def test_audit_clean_schema_scores_100() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Clean API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/users",
                method="GET",
                summary="List all users",
                auth_required=True,
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, example=[{"id": "1", "name": "Alice"}])
                ),
            ),
            Endpoint(
                path="/users/{id}",
                method="GET",
                summary="Retrieve user details",
                auth_required=True,
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, example={"id": "1", "name": "Alice"})
                ),
            ),
            Endpoint(
                path="/users/{id}",
                method="DELETE",
                summary="Delete user account",
                auth_required=True,
                responses=EndpointResponses(success=ResponseSuccess(status=204)),
            ),
        ],
    )

    service = AuditService()
    report = service.audit(schema)

    assert report.total_endpoints == 3
    assert report.total_issues == 0
    assert report.coherence_score == 100.0
    assert report.has_issues is False


def test_audit_inc001_verb_mismatch() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Incoherent API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/accounts",
                method="GET",
                summary="Delete user account",
                auth_required=True,
                responses=EndpointResponses(success=ResponseSuccess(status=200)),
            ),
            Endpoint(
                path="/orders/{id}",
                method="DELETE",
                summary="Get order details",
                auth_required=True,
                responses=EndpointResponses(success=ResponseSuccess(status=204)),
            ),
        ],
    )

    service = AuditService()
    report = service.audit(schema)

    inc001_issues = [i for i in report.issues if i.code == "INC001"]
    assert len(inc001_issues) == 2
    assert any("GET endpoint has mutation verb" in i.message for i in inc001_issues)
    assert any("DELETE endpoint has retrieval verb" in i.message for i in inc001_issues)


def test_audit_inc002_status_code_inconsistency() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Status Inconsistency API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/items",
                method="GET",
                summary="List items",
                auth_required=True,
                responses=EndpointResponses(
                    success=ResponseSuccess(status=204, example={"unexpected": "body"})
                ),
            ),
            Endpoint(
                path="/reports",
                method="GET",
                summary="Fetch reports",
                auth_required=True,
                responses=EndpointResponses(success=ResponseSuccess(status=201)),
            ),
        ],
    )

    service = AuditService()
    report = service.audit(schema)

    inc002_issues = [i for i in report.issues if i.code == "INC002"]
    assert len(inc002_issues) == 2
    assert any("204" in i.message for i in inc002_issues)
    assert any("201" in i.message for i in inc002_issues)


def test_audit_inc003_path_plurality_mismatch() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Plurality API", version="1.0.0"),
        endpoints=[
            # Collection /products returns a single object without items/results keys
            Endpoint(
                path="/products",
                method="GET",
                summary="List products",
                auth_required=True,
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, example={"single_id": "123"})
                ),
            ),
            # Single-item /products/{id} returns an array
            Endpoint(
                path="/products/{id}",
                method="GET",
                summary="Get product",
                auth_required=True,
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, example=[{"id": "123"}])
                ),
            ),
        ],
    )

    service = AuditService()
    report = service.audit(schema)

    inc003_issues = [i for i in report.issues if i.code == "INC003"]
    assert len(inc003_issues) == 2


def test_audit_inc004_public_destructive_endpoints() -> None:
    schema = TeraSchema(
        api=ApiConfig(name="Security Inconsistency API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/items/{id}",
                method="DELETE",
                summary="Delete item",
                auth_required=False,  # Unauthenticated DELETE!
                responses=EndpointResponses(success=ResponseSuccess(status=204)),
            ),
        ],
    )

    service = AuditService()
    report = service.audit(schema)

    inc004_issues = [i for i in report.issues if i.code == "INC004"]
    assert len(inc004_issues) == 1
    assert inc004_issues[0].severity == "CRITICAL"
    assert report.has_critical is True
    assert report.coherence_score <= 80.0
