from typing import List, Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict

HTTPMethod = Literal['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']
AuthType = Literal['bearer', 'basic', 'apikey']

class BaseField(BaseModel):
    """
    Essencial content of data
    """
    model_config = ConfigDict(extra='forbid')

    name: str
    type: str = "string"
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

    query: List[ParamField] = Field(default_factory=list)
    path: List[ParamField] = Field(default_factory=list)
    header: List[ParamField] = Field(default_factory=list)

class ResponseSuccess(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: int = 200
    description: str = "Sucesso"
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
    errors: List[ResponseError] = Field(default_factory=list)

class Endpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')

    path: str
    method: HTTPMethod
    summary: str
    tag: Optional[str] = None
    description: Optional[str] = None
    auth_required: bool = False
    params: Optional[EndpointParams] = None
    body: List[BodyField] = Field(default_factory=list)
    responses: EndpointResponses

class TeraSchema(BaseModel):
    """
    Root schema, representing the entire API.
    """
    model_config = ConfigDict(extra='forbid')

    api: ApiConfig
    endpoints: List[Endpoint]