from tera.core.converter import TeraConverter

def test_basic_conversion_structure(minimal_schema_model):
    """Testa se a estrutura básica do OpenAPI é gerada corretamente."""
    converter = TeraConverter(minimal_schema_model)
    result = converter.convert()

    assert result["openapi"] == "3.0.3"
    assert result["info"]["title"] == "Test API"
    assert result["paths"]["/test"]["get"]["operationId"] == "getTest"

def test_inference_primitive_types(minimal_schema_model):
    """Testa se strings, ints e bools são inferidos corretamente."""
    converter = TeraConverter(minimal_schema_model)
    
    # Teste isolado do método privado de inferência
    assert converter._infer_schema_recursive("texto") == {"type": "string"}
    assert converter._infer_schema_recursive(123) == {"type": "integer"}
    assert converter._infer_schema_recursive(True) == {"type": "boolean"}

def test_inference_nested_object(minimal_schema_model):
    """Testa a RECURSÃO: Objeto dentro de objeto."""
    converter = TeraConverter(minimal_schema_model)
    
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
    # Verifica o nível mais profundo
    assert schema["properties"]["user"]["properties"]["age"]["type"] == "integer"

def test_inference_array(minimal_schema_model):
    """Testa se listas são convertidas para arrays tipados."""
    converter = TeraConverter(minimal_schema_model)
    
    list_data = ["item1", "item2"]
    schema = converter._infer_schema_recursive(list_data)
    
    assert schema["type"] == "array"
    assert schema["items"]["type"] == "string"