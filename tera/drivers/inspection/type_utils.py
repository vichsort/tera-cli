import dataclasses
from typing import Any, Dict
try:
    from pydantic import BaseModel
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    BaseModel = None

def is_pydantic_model(type_hint: Any) -> bool:
    """
    Verifies if the type passed is a Pydantic class (BaseModel).
    Safe to call even without Pydantic installed.
    """
    if not HAS_PYDANTIC:
        return False
    
    if not isinstance(type_hint, type):
        return False
        
    return issubclass(type_hint, BaseModel)

def get_pydantic_schema(model_class: Any) -> Dict[str, Any]:
    """
    Extracts JSON Schema from a Pydantic model.
    Supports Pydantic V2 (model_json_schema) and V1 (schema).
    """
    if not is_pydantic_model(model_class):
        return {}

    # Pydantic V2
    if hasattr(model_class, "model_json_schema"):
        return model_class.model_json_schema()
    
    # Pydantic V1
    if hasattr(model_class, "schema"):
        return model_class.schema()

    return {}

def is_dataclass(type_hint: Any) -> bool:
    """Verifies if is a native Python Dataclass."""
    return dataclasses.is_dataclass(type_hint) and isinstance(type_hint, type)