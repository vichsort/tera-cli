from typing import Any, Dict, List
from ..models.inputs import TeraSchema, ParamField, BodyField

class TeraConverter:
    def __init__(self, schema: TeraSchema):
        self.schema = schema
        self.openapi_version = "3.0.3"

    def convert(self) -> Dict[str, Any]:
        """
        Método principal que orquestra a conversão.
        Retorna um dicionário pronto para ser dumpado como JSON.
        """
        return {
            "openapi": self.openapi_version,
            "info": {
                "title": self.schema.api.name,
                "version": self.schema.api.version,
                "description": self.schema.api.description,
            },
            "servers": [
                {"url": self.schema.api.base_url}
            ],
            "components": self._build_components(),
            "paths": self._build_paths(),
        }

    def _build_components(self) -> Dict[str, Any]:
        """Gera os esquemas de segurança se necessário."""
        components = {}
        
        # Se houver config de auth, adiciona o Security Scheme
        if self.schema.api.auth:
            scheme_type = self.schema.api.auth.type
            if scheme_type == "bearer":
                components["securitySchemes"] = {
                    "bearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT"
                    }
                }
            # Aqui poderíamos expandir para apikey/basic no futuro
            
        return components

    def _build_paths(self) -> Dict[str, Any]:
        """Transforma a lista de endpoints no formato de árvore do OpenAPI."""
        paths = {}

        for ep in self.schema.endpoints:
            if ep.path not in paths:
                paths[ep.path] = {}

            # gera o operationId (ex: GET /users -> getUsers)
            operation_id = self._generate_operation_id(ep.method, ep.path)
            
            operation = {
                "summary": ep.summary,
                "operationId": operation_id,
                "tags": [ep.tag] if ep.tag else [],
                "description": ep.description,
                "parameters": [],
                "responses": {}
            }

            # Autenticação
            if ep.auth_required and self.schema.api.auth:
                scheme_name = f"{self.schema.api.auth.type}Auth" # ex: bearerAuth
                operation["security"] = [{scheme_name: []}]

            # Parâmetros (Query, Path, Header)
            if ep.params:
                for p in ep.params.path:
                    operation["parameters"].append(self._build_parameter(p, "path"))
                for p in ep.params.query:
                    operation["parameters"].append(self._build_parameter(p, "query"))
                for p in ep.params.header:
                    operation["parameters"].append(self._build_parameter(p, "header"))

            # Request Body (Apenas para POST/PUT/PATCH)
            if ep.body and ep.method in ["POST", "PUT", "PATCH"]:
                operation["requestBody"] = self._build_request_body(ep.body)

            # respostas
            operation["responses"] = self._build_responses(ep.responses)

            paths[ep.path][ep.method.lower()] = operation

        return paths

    def _build_parameter(self, param: ParamField, location: str) -> Dict[str, Any]:
        """Monta o objeto de parâmetro individual."""
        schema = self._infer_schema_recursive(param.example)
        
        if param.min_length is not None:
            schema["minLength"] = param.min_length
        if param.max_length is not None:
            schema["maxLength"] = param.max_length

        return {
            "name": param.name,
            "in": location,
            "required": param.required,
            "description": param.description,
            "schema": schema
        }

    def _build_request_body(self, fields: List[BodyField]) -> Dict[str, Any]:
        """
        Converte a lista de campos do Body num Schema Object do OpenAPI.
        """
        properties = {}
        required_fields = []

        for field in fields:
            properties[field.name] = self._infer_schema_recursive(field.example)
            
            if field.description:
                properties[field.name]["description"] = field.description
                
            if field.required:
                required_fields.append(field.name)

        schema = {
            "type": "object",
            "properties": properties
        }
        if required_fields:
            schema["required"] = required_fields

        # Monta o exemplo completo para exibir na doc
        full_example = {f.name: f.example for f in fields}

        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": schema,
                    "example": full_example
                }
            }
        }

    def _build_responses(self, responses) -> Dict[str, Any]:
        """Monta o dicionário de responses."""
        output = {}

        success_schema = self._infer_schema_recursive(responses.success.example)
        output[str(responses.success.status)] = {
            "description": responses.success.description,
            "content": {
                "application/json": {
                    "schema": success_schema,
                    "example": responses.success.example
                }
            }
        }

        # Error Responses
        for error in responses.errors:
            # Se o usuário não deu exemplo de erro, criamos um genérico
            example = error.example if error.example else {"message": error.message}
            err_schema = self._infer_schema_recursive(example)
            
            output[str(error.status)] = {
                "description": error.message,
                "content": {
                    "application/json": {
                        "schema": err_schema,
                        "example": example
                    }
                }
            }

        return output

    def _infer_schema_recursive(self, data: Any) -> Dict[str, Any]:
        """
        Recebe um dado (example) e infere a estrutura JSON Schema recursivamente.
        """
        if isinstance(data, bool):
            return {"type": "boolean"}
        
        elif isinstance(data, int):
            return {"type": "integer"}
        
        elif isinstance(data, float):
            return {"type": "number"}
        
        elif isinstance(data, str):
            return {"type": "string"}
        
        elif isinstance(data, dict):
            # Recursão para Objetos
            properties = {k: self._infer_schema_recursive(v) for k, v in data.items()}
            return {
                "type": "object",
                "properties": properties
            }
        
        elif isinstance(data, list):
            # Recursão para Arrays
            if not data:
                return {"type": "array", "items": {}} # Lista vazia
            
            # Pega o primeiro item para inferir o tipo da lista
            return {
                "type": "array",
                "items": self._infer_schema_recursive(data[0])
            }
        
        elif data is None:
            return {"type": "string", "nullable": True}

        return {"type": "string"}

    def _generate_operation_id(self, method: str, path: str) -> str:
        """Gera um ID único: GET /users/search -> getUsersSearch"""
        # Limpa parâmetros de rota {id}
        clean_path = path.replace("{", "").replace("}", "").replace("/", "_")
        # Remove underscore inicial se houver
        if clean_path.startswith("_"):
            clean_path = clean_path[1:]
        
        # Converte snake_case para camelCase simples
        parts = clean_path.split("_")
        camel_path = "".join(x.capitalize() for x in parts)
        
        return f"{method.lower()}{camel_path}"