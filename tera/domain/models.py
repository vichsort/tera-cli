from typing import List, Optional, Any, Literal, Dict, Tuple
from pydantic import BaseModel, Field, ConfigDict, field_validator

HTTPMethod = Literal['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
AuthType = Literal['bearer', 'basic', 'apikey']
FieldType = Literal['string', 'number', 'integer', 'boolean', 'array', 'object']

class BaseField(BaseModel):
    """
    Essential data field definition.
    """
    model_config = ConfigDict(extra='forbid')

    name: str
    type: FieldType = "string"
    example: Any = None
    required: bool = False
    description: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None

class ParamField(BaseField):
    pass

class BodyField(BaseField):
    pass

class AuthConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    type: AuthType

class ApiConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    version: str
    description: Optional[str] = None
    base_url: Optional[str] = "/"
    auth: Optional[AuthConfig] = None

class EndpointParams(BaseModel):
    model_config = ConfigDict(extra='forbid')

    query: List[ParamField] = Field(default_factory=list[ParamField])
    path: List[ParamField] = Field(default_factory=list[ParamField])
    header: List[ParamField] = Field(default_factory=list[ParamField])

    @property
    def all_params(self) -> List[ParamField]:
        return self.query + self.path + self.header

class ResponseSuccess(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: int = 200
    description: str = "Success"
    example: Any = None

class ResponseError(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: int
    message: str
    description: Optional[str] = None
    example: Optional[Any] = None

class EndpointResponses(BaseModel):
    model_config = ConfigDict(extra='forbid')

    success: ResponseSuccess
    errors: List[ResponseError] = Field(default_factory=list[ResponseError])

class Endpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')

    path: str
    method: HTTPMethod
    summary: str
    tag: Optional[str] = None
    description: Optional[str] = None
    auth_required: bool = False
    params: Optional[EndpointParams] = None
    body: List[BodyField] = Field(default_factory=list[BodyField])
    responses: EndpointResponses

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.upper()
        return v

    @property
    def key(self) -> Tuple[str, str]:
        return (self.method, self.path)

    @property
    def identifier(self) -> str:
        return f"{self.method} {self.path}"

class TeraSchema(BaseModel):
    """
    Root schema, representing the entire API.
    """
    model_config = ConfigDict(extra='forbid')

    api: ApiConfig
    endpoints: List[Endpoint]

    @property
    def endpoint_map(self) -> Dict[Tuple[str, str], Endpoint]:
        return {ep.key: ep for ep in self.endpoints}

    def get_endpoint(self, method: str, path: str) -> Optional[Endpoint]:
        return self.endpoint_map.get((method.upper(), path))