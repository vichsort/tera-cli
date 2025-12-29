import pytest
from tera.models.inputs import TeraSchema, Endpoint, ResponseSuccess, EndpointResponses

@pytest.fixture
def minimal_schema_model():
    """Retorna um objeto TeraSchema válido e minimalista para testes unitários."""
    return TeraSchema(
        api={
            "name": "Test API", 
            "version": "1.0",
            "auth": {"type": "bearer"}
        },
        endpoints=[
            Endpoint(
                path="/test",
                method="GET",
                summary="Test Endpoint",
                responses=EndpointResponses(
                    success=ResponseSuccess(
                        status=200,
                        example={"msg": "ok"} # Exemplo simples
                    )
                )
            )
        ]
    )