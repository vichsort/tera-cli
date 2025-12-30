from typing import Any, Dict, List
import re
from tera.domain.models import TeraSchema, Endpoint, ParamField, BodyField

class TeraOpenApiAdapter:
    """
    Adapter responsible for translating the Domain (TeraSchema)
    for an dict compatible with the OpenAPI 3.0 Spec.
    """
    def __init__(self, schema: TeraSchema):
        self.schema = schema

    def convert(self) -> Dict[str, Any]:
        """Generates complete OpenAPI JSON."""
        return {
            "openapi": "3.0.3",
            "info": {
                "title": self.schema.api.name,
                "version": self.schema.api.version,
                "description": self.schema.api.description,
            },
            "servers": [
                {"url": self.schema.api.base_url or "/"}
            ],
            "components": {
                "securitySchemes": self._build_security_schemes()
            },
            "paths": self._build_paths()
        }

    def _build_security_schemes(self) -> Dict[str, Any]:
        if not self.schema.api.auth:
            return {}
        
        auth_type = self.schema.api.auth.type
        if auth_type == "bearer":
            return {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # ! Futuro: Adicionar basic/apikey aqui !
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        return {}

    def _build_paths(self) -> Dict[str, Any]:
        paths = {}
        for ep in self.schema.endpoints:
            path_item = paths.get(ep.path, {})
            method_lower = ep.method.lower()
            
            operation = {
                "summary": ep.summary,
                "operationId": self._generate_operation_id(ep),
                "tags": [ep.tag] if ep.tag else [],
                "description": ep.description,
                "parameters": self._build_parameters(ep),
                "responses": self._build_responses(ep)
            }

            # Security on endpoint
            if ep.auth_required:
                operation["security"] = [{"bearerAuth": []}]

            # Request Body
            if ep.body:
                operation["requestBody"] = self._build_request_body(ep.body)

            path_item[method_lower] = operation
            paths[ep.path] = path_item
        
        return paths

    def _generate_operation_id(self, ep: Endpoint) -> str:
        """Generates IDs as 'getUsersId' based on verbs and path."""
        clean_path = re.sub(r'\{.*?\}', '', ep.path)
        clean_path = re.sub(r'[^a-zA-Z0-9]', ' ', clean_path)
        words = clean_path.split()
        camel_case = ''.join(word.capitalize() for word in words)
        return f"{ep.method.lower()}{camel_case}"

    def _build_parameters(self, ep: Endpoint) -> List[Dict[str, Any]]:
        openapi_params = []
        
        if not ep.params:
            return openapi_params

        def add_params(fields: List[ParamField], location: str):
            for field in fields:
                param = {
                    "name": field.name,
                    "in": location,
                    "required": field.required,
                    "description": field.description,
                    "schema": self._infer_schema_recursive(field.example)
                }
                if field.min_length is not None:
                    param["schema"]["minLength"] = field.min_length
                
                openapi_params.append(param)

        add_params(ep.params.path, "path")
        add_params(ep.params.query, "query")
        add_params(ep.params.header, "header")
        
        return openapi_params

    def _build_request_body(self, body_fields: List[BodyField]) -> Dict[str, Any]:
        properties = {}
        required_fields = []
        example_dict = {}

        for field in body_fields:
            properties[field.name] = self._infer_schema_recursive(field.example)
            if field.required:
                required_fields.append(field.name)
            example_dict[field.name] = field.example

        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required_fields if required_fields else None
                    },
                    "example": example_dict
                }
            }
        }

    def _build_responses(self, ep: Endpoint) -> Dict[str, Any]:
        responses = {}
        
        success_schema = self._infer_schema_recursive(ep.responses.success.example)
        responses[str(ep.responses.success.status)] = {
            "description": ep.responses.success.description,
            "content": {
                "application/json": {
                    "schema": success_schema,
                    "example": ep.responses.success.example
                }
            }
        }

        for err in ep.responses.errors:
            error_schema = self._infer_schema_recursive(err.example) if err.example else {"type": "object"}
            responses[str(err.status)] = {
                "description": err.message,
                "content": {
                    "application/json": {
                        "schema": error_schema,
                        "example": err.example
                    }
                }
            }

        return responses

    def _infer_schema_recursive(self, value: Any) -> Dict[str, Any]:
        """
        The brain of inference: Receives a Python value (str, int, dict, list)
        and returns the corresponding OpenAPI Schema.
        """
        if isinstance(value, str):
            if len(value) == 36 and re.match(r'^[0-9a-fA-F-]{36}$', value):
                return {"type": "string", "format": "uuid"}
            return {"type": "string"}
        
        if isinstance(value, bool):
            return {"type": "boolean"}
        
        if isinstance(value, int):
            return {"type": "integer"}
        
        if isinstance(value, float):
            return {"type": "number"}

        if isinstance(value, dict):
            properties = {k: self._infer_schema_recursive(v) for k, v in value.items()}
            return {"type": "object", "properties": properties}

        if isinstance(value, list):
            if not value:
                return {"type": "array", "items": {}}
            item_schema = self._infer_schema_recursive(value[0])
            return {"type": "array", "items": item_schema}

        return {"type": "string"}