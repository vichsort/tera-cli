from pydantic import BaseModel
from typing import List, Dict
from tera.drivers.flask_driver import FlaskAppDriver

class SampleModel(BaseModel):
    id: int
    name: str
    is_active: bool
    score: float
    tags: List[str]
    metadata: Dict[str, str]

def test_extract_pydantic_fields_types():
    driver = FlaskAppDriver("dummy:app")
    fields = driver._extract_pydantic_fields(SampleModel)
    field_map = {f.name: f for f in fields}

    assert field_map["id"].type == "integer"
    assert field_map["id"].example == 0

    assert field_map["name"].type == "string"
    assert field_map["name"].example == "string"

    assert field_map["is_active"].type == "boolean"
    assert field_map["is_active"].example is True

    assert field_map["score"].type == "number"
    assert field_map["score"].example == 0.0

    assert field_map["tags"].type == "array"
    assert field_map["tags"].example == []

    assert field_map["metadata"].type == "object"
    assert field_map["metadata"].example == {}

def test_map_type_hint_to_field_type():
    driver = FlaskAppDriver("dummy:app")

    assert driver._map_type_hint_to_field_type(int) == "integer"
    assert driver._map_type_hint_to_field_type(float) == "number"
    assert driver._map_type_hint_to_field_type(bool) == "boolean"
    assert driver._map_type_hint_to_field_type(list) == "array"
    assert driver._map_type_hint_to_field_type(dict) == "object"
    assert driver._map_type_hint_to_field_type(str) == "string"

