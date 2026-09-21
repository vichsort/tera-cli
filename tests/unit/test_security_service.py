import pytest
from tera.domain import (
    TeraSchema,
    ApiConfig,
    Endpoint,
    EndpointResponses,
    ResponseSuccess
)
from tera.services import SecurityDriftService

@pytest.fixture
def clean_doc() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="Security API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/public",
                method="GET",
                summary="Public endpoint",
                auth_required=False,
                responses=EndpointResponses(success=ResponseSuccess(status=200))
            ),
            Endpoint(
                path="/private",
                method="GET",
                summary="Private endpoint",
                auth_required=True,
                responses=EndpointResponses(success=ResponseSuccess(status=200))
            )
        ]
    )

@pytest.fixture
def matching_code() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="Flask App", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/public",
                method="GET",
                summary="Public endpoint",
                auth_required=False,
                responses=EndpointResponses(success=ResponseSuccess(status=200))
            ),
            Endpoint(
                path="/private",
                method="GET",
                summary="Private endpoint",
                auth_required=True,
                responses=EndpointResponses(success=ResponseSuccess(status=200))
            )
        ]
    )

def test_security_audit_no_drift(clean_doc: TeraSchema, matching_code: TeraSchema) -> None:
    service = SecurityDriftService()
    report = service.audit(matching_code, clean_doc)

    assert report.has_drift is False
    assert report.critical_count == 0
    assert report.warning_count == 0
    assert len(report.issues) == 0

def test_security_missing_auth_in_code(clean_doc: TeraSchema, matching_code: TeraSchema) -> None:
    # Code loses auth on /private
    matching_code.endpoints[1].auth_required = False

    service = SecurityDriftService()
    report = service.audit(matching_code, clean_doc)

    assert report.has_drift is True
    assert report.critical_count == 1
    issue = report.issues[0]
    assert issue.drift_type == "missing_auth_in_code"
    assert issue.severity == "CRITICAL"
    assert issue.path == "/private"

def test_security_missing_auth_in_doc(clean_doc: TeraSchema, matching_code: TeraSchema) -> None:
    # Code adds auth to /public
    matching_code.endpoints[0].auth_required = True

    service = SecurityDriftService()
    report = service.audit(matching_code, clean_doc)

    assert report.has_drift is True
    assert report.critical_count == 1
    issue = report.issues[0]
    assert issue.drift_type == "missing_auth_in_doc"
    assert issue.severity == "CRITICAL"
    assert issue.path == "/public"

def test_security_undocumented_secure_endpoint(clean_doc: TeraSchema, matching_code: TeraSchema) -> None:
    # Code has a new secure endpoint not in docs
    matching_code.endpoints.append(
        Endpoint(
            path="/admin",
            method="POST",
            summary="Admin endpoint",
            auth_required=True,
            responses=EndpointResponses(success=ResponseSuccess(status=200))
        )
    )

    service = SecurityDriftService()
    report = service.audit(matching_code, clean_doc)

    assert report.has_drift is True
    assert report.warning_count == 1
    issue = next(i for i in report.issues if i.path == "/admin")
    assert issue.drift_type == "undocumented_endpoint"
    assert issue.severity == "WARNING"
