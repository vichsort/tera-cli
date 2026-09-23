import pytest
from tera.domain.models import TeraSchema, Endpoint, ResponseSuccess, EndpointResponses, ApiConfig, AuthConfig

@pytest.fixture
def minimal_schema_model() -> TeraSchema:
    """Returns a valid and minimalist TeraSchema object for unit tests."""
    return TeraSchema(
        api=ApiConfig(
            name="Test API", 
            version="1.0",
            auth=AuthConfig(type="bearer")
        ),
        endpoints=[
            Endpoint(
                path="/test",
                method="GET",
                summary="Test Endpoint",
                responses=EndpointResponses(
                    success=ResponseSuccess(
                        status=200,
                        example={"msg": "ok"}
                    )
                )
            )
        ]
    )