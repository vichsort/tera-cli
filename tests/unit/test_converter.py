# pyright: reportPrivateUsage=false
from tera.adapters.openapi import TeraOpenApiAdapter
from tera.domain.models import TeraSchema

def test_basic_conversion_structure(minimal_schema_model: TeraSchema) -> None:
    """Tests if the basic OpenAPI structure is generated correctly."""
    converter = TeraOpenApiAdapter(minimal_schema_model)
    result = converter.convert()

    assert result["openapi"] == "3.0.3"
    assert result["info"]["title"] == "Test API"
    assert result["paths"]["/test"]["get"]["operationId"] == "getTest"

def test_inference_primitive_types(minimal_schema_model: TeraSchema) -> None:
    """Tests if strings, integers and booleans are inferred correctly."""
    converter = TeraOpenApiAdapter(minimal_schema_model)
    
    # Isolated test of private schema inference method
    assert converter._infer_schema_recursive("texto") == {"type": "string"}
    assert converter._infer_schema_recursive(123) == {"type": "integer"}
    assert converter._infer_schema_recursive(True) == {"type": "boolean"}

def test_inference_nested_object(minimal_schema_model: TeraSchema) -> None:
    """Tests recursive schema inference on nested dictionary objects."""
    converter = TeraOpenApiAdapter(minimal_schema_model)
    
    complex_data = {
        "user": {
            "name": "Wolnei",
            "age": 30
        }
    }
    
    schema = converter._infer_schema_recursive(complex_data)
    
    assert schema["type"] == "object"
    assert "user" in schema["properties"]
    assert schema["properties"]["user"]["type"] == "object"
    # Verify deepest nested field
    assert schema["properties"]["user"]["properties"]["age"]["type"] == "integer"

def test_inference_array(minimal_schema_model: TeraSchema) -> None:
    """Tests if lists are converted into typed arrays."""
    converter = TeraOpenApiAdapter(minimal_schema_model)
    
    list_data = ["item1", "item2"]
    schema = converter._infer_schema_recursive(list_data)
    
    assert schema["type"] == "array"
    assert schema["items"]["type"] == "string"