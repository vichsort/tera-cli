import pytest
from tera.domain.models import TeraSchema, Endpoint, ResponseSuccess, EndpointResponses, ApiConfig, AuthConfig

@pytest.fixture
def minimal_schema_model() -> TeraSchema:
    """Retorna um objeto TeraSchema válido e minimalista para testes unitários."""
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