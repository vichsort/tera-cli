from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, cast
import json
import yaml

from tera.contracts import TeraDriver
from tera.domain.models import (
    ApiConfig,
    AuthConfig,
    AuthType,
    BodyField,
    Endpoint,
    EndpointParams,
    EndpointResponses,
    FieldType,
    HTTPMethod,
    ParamField,
    ResponseError,
    ResponseSuccess,
    TeraSchema,
)
from tera.exceptions import TeraError

SUPPORTED_HTTP_METHODS: Set[str] = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
VALID_FIELD_TYPES: Set[str] = {"string", "number", "integer", "boolean", "array", "object"}


def _as_dict(val: Any) -> Dict[str, Any]:
    if isinstance(val, dict):
        return cast(Dict[str, Any], val)
    return {}


def _as_list(val: Any) -> List[Any]:
    if isinstance(val, list):
        return cast(List[Any], val)
    return []


class OpenApiDriver(TeraDriver):
    """
    Input driver that reads an OpenAPI (3.0.x / 3.1.x) or Swagger 2.0 specification
    from a file (JSON or YAML) and converts it into a canonical TeraSchema.
    """

    def __init__(self, source: Union[Path, str, Dict[str, Any]]) -> None:
        self.source: Union[Path, str, Dict[str, Any]] = source
        self.raw_data: Dict[str, Any] = {}

    def load(self) -> TeraSchema:
        self.raw_data = self._load_raw_data()
        return self._parse_schema()

    def _load_raw_data(self) -> Dict[str, Any]:
        if isinstance(self.source, dict):
            return self.source

        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"OpenAPI file '{path}' not found.")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            raise TeraError("File Read Error", f"Could not read '{path}': {e}")

        if path.suffix.lower() == ".json":
            try:
                data: Any = json.loads(content)
                if isinstance(data, dict):
                    return cast(Dict[str, Any], data)
                raise ValueError("JSON root must be an object.")
            except Exception as e:
                raise TeraError("JSON Parsing Error", f"Invalid JSON in '{path}': {e}")

        try:
            data_yaml: Any = yaml.safe_load(content)
            if isinstance(data_yaml, dict):
                return cast(Dict[str, Any], data_yaml)
            raise ValueError("YAML root must be an object mapping.")
        except yaml.YAMLError as e:
            raise TeraError("YAML Parsing Error", f"Invalid YAML in '{path}': {e}")
        except Exception as e:
            raise TeraError("OpenAPI Load Error", f"Could not parse '{path}': {e}")

    def _resolve_ref(self, ref: str) -> Dict[str, Any]:
        if not ref.startswith("#/"):
            return {}
        parts = ref.lstrip("#/").split("/")
        current = self.raw_data
        for part in parts:
            if part in current:
                val = current[part]
                if isinstance(val, dict):
                    current = _as_dict(val)
                else:
                    return {}
            else:
                return {}
        return current

    def _resolve_schema(self, schema_or_ref: Dict[str, Any]) -> Dict[str, Any]:
        ref_val = schema_or_ref.get("$ref")
        if isinstance(ref_val, str):
            resolved = self._resolve_ref(ref_val)
            merged = dict(resolved)
            for k, v in schema_or_ref.items():
                if k != "$ref":
                    merged[str(k)] = v
            return merged
        return schema_or_ref

    def _map_field_type(self, raw_type: Any) -> FieldType:
        if isinstance(raw_type, list):
            raw_list = cast(List[Any], raw_type)
            if len(raw_list) > 0:
                raw_type = raw_list[0]
        if isinstance(raw_type, str) and raw_type in VALID_FIELD_TYPES:
            return cast(FieldType, raw_type)
        return "string"

    def _parse_api_config(self) -> ApiConfig:
        info = _as_dict(self.raw_data.get("info"))
        title = str(info.get("title") or "Imported API")
        version = str(info.get("version") or "1.0.0")
        description_raw = info.get("description")
        description = str(description_raw) if description_raw is not None else None

        base_url = "/"
        servers = _as_list(self.raw_data.get("servers"))
        if len(servers) > 0 and isinstance(servers[0], dict):
            first_server = _as_dict(servers[0])
            first_url = first_server.get("url")
            if first_url:
                base_url = str(first_url)
        elif "basePath" in self.raw_data:
            base_url = str(self.raw_data["basePath"])

        auth_config: Optional[AuthConfig] = None
        components = _as_dict(self.raw_data.get("components"))
        sec_schemes = _as_dict(components.get("securitySchemes"))
        if not sec_schemes and "securityDefinitions" in self.raw_data:
            sec_schemes = _as_dict(self.raw_data.get("securityDefinitions"))

        for _, raw_scheme in sec_schemes.items():
            if isinstance(raw_scheme, dict):
                scheme_def = self._resolve_schema(_as_dict(raw_scheme))
                stype = str(scheme_def.get("type", "")).lower()
                scheme = str(scheme_def.get("scheme", "")).lower()
                if stype == "http" and scheme == "bearer":
                    auth_config = AuthConfig(type=cast(AuthType, "bearer"))
                    break
                elif stype == "http" and scheme == "basic":
                    auth_config = AuthConfig(type=cast(AuthType, "basic"))
                    break
                elif stype in ("apikey", "api_key"):
                    auth_config = AuthConfig(type=cast(AuthType, "apikey"))
                    break
                elif stype == "basic":
                    auth_config = AuthConfig(type=cast(AuthType, "basic"))
                    break
                elif stype == "bearer":
                    auth_config = AuthConfig(type=cast(AuthType, "bearer"))
                    break

        return ApiConfig(
            name=title,
            version=version,
            description=description,
            base_url=base_url,
            auth=auth_config,
        )

    def _parse_schema(self) -> TeraSchema:
        api = self._parse_api_config()
        endpoints: List[Endpoint] = []

        paths_dict = _as_dict(self.raw_data.get("paths"))
        global_security = _as_list(self.raw_data.get("security"))
        has_global_security = len(global_security) > 0

        for path_str, raw_path_item in paths_dict.items():
            path_item = self._resolve_schema(_as_dict(raw_path_item))
            path_level_params = _as_list(path_item.get("parameters"))

            for method_str, raw_op in path_item.items():
                method_upper = str(method_str).upper()
                if method_upper not in SUPPORTED_HTTP_METHODS:
                    continue
                if not isinstance(raw_op, dict):
                    continue

                op_dict = self._resolve_schema(_as_dict(raw_op))
                endpoint = self._parse_endpoint(
                    path=str(path_str),
                    method=cast(HTTPMethod, method_upper),
                    operation=op_dict,
                    path_params=path_level_params,
                    has_global_security=has_global_security,
                )
                endpoints.append(endpoint)

        return TeraSchema(api=api, endpoints=endpoints)

    def _parse_endpoint(
        self,
        path: str,
        method: HTTPMethod,
        operation: Dict[str, Any],
        path_params: List[Any],
        has_global_security: bool,
    ) -> Endpoint:
        summary = str(operation.get("summary") or f"{method} {path}")
        description_raw = operation.get("description")
        description = str(description_raw) if description_raw is not None else None

        tags = _as_list(operation.get("tags"))
        tag: Optional[str] = None
        if len(tags) > 0 and isinstance(tags[0], str):
            tag = tags[0]

        # Security
        auth_required = False
        if "security" in operation:
            sec = _as_list(operation.get("security"))
            auth_required = len(sec) > 0
        elif has_global_security:
            auth_required = True

        combined_params: Dict[str, Dict[str, Any]] = {}

        for p in path_params:
            if isinstance(p, dict):
                p_resolved = self._resolve_schema(_as_dict(p))
                p_name = str(p_resolved.get("name", ""))
                p_in = str(p_resolved.get("in", ""))
                if p_name and p_in:
                    combined_params[f"{p_in}:{p_name}"] = p_resolved

        op_params = _as_list(operation.get("parameters"))
        for p in op_params:
            if isinstance(p, dict):
                p_resolved = self._resolve_schema(_as_dict(p))
                p_name = str(p_resolved.get("name", ""))
                p_in = str(p_resolved.get("in", ""))
                if p_name and p_in:
                    combined_params[f"{p_in}:{p_name}"] = p_resolved

        path_fields: List[ParamField] = []
        query_fields: List[ParamField] = []
        header_fields: List[ParamField] = []
        body_fields: List[BodyField] = []

        for p_resolved in combined_params.values():
            p_in = str(p_resolved.get("in", "")).lower()
            p_name = str(p_resolved.get("name", ""))

            if p_in == "body":
                b_schema = _as_dict(p_resolved.get("schema"))
                body_fields.extend(self._extract_body_fields(b_schema))
                continue

            raw_schema = p_resolved.get("schema")
            if isinstance(raw_schema, dict):
                schema = self._resolve_schema(_as_dict(raw_schema))
            else:
                schema = p_resolved

            ftype = self._map_field_type(schema.get("type", p_resolved.get("type", "string")))
            example: Any = p_resolved.get("example", schema.get("example"))
            p_desc_raw = p_resolved.get("description")
            p_desc = str(p_desc_raw) if p_desc_raw is not None else None
            min_len = schema.get("minLength")
            max_len = schema.get("maxLength")

            is_required = bool(p_resolved.get("required", True if p_in == "path" else False))

            field = ParamField(
                name=p_name,
                type=ftype,
                example=example,
                required=is_required,
                description=p_desc,
                min_length=int(min_len) if isinstance(min_len, int) else None,
                max_length=int(max_len) if isinstance(max_len, int) else None,
            )

            if p_in == "path":
                path_fields.append(field)
            elif p_in == "query":
                query_fields.append(field)
            elif p_in == "header":
                header_fields.append(field)

        request_body = _as_dict(operation.get("requestBody"))
        if request_body:
            request_body_resolved = self._resolve_schema(request_body)
            content = _as_dict(request_body_resolved.get("content"))
            if content:
                json_content_raw = content.get("application/json")
                if json_content_raw is None and len(content) > 0:
                    json_content_raw = next(iter(content.values()))
                json_content = _as_dict(json_content_raw)
                b_schema = _as_dict(json_content.get("schema"))
                if b_schema:
                    body_fields.extend(self._extract_body_fields(b_schema))

        params_obj: Optional[EndpointParams] = None
        if path_fields or query_fields or header_fields:
            params_obj = EndpointParams(path=path_fields, query=query_fields, header=header_fields)

        responses_obj = self._parse_responses(_as_dict(operation.get("responses")))

        return Endpoint(
            path=path,
            method=method,
            summary=summary,
            tag=tag,
            description=description,
            auth_required=auth_required,
            params=params_obj,
            body=body_fields,
            responses=responses_obj,
        )

    def _extract_body_fields(self, schema: Dict[str, Any]) -> List[BodyField]:
        resolved_schema = self._resolve_schema(schema)
        properties = _as_dict(resolved_schema.get("properties"))
        if not properties:
            return []

        required_set: Set[str] = set()
        raw_required = _as_list(resolved_schema.get("required"))
        for item in raw_required:
            required_set.add(str(item))

        fields: List[BodyField] = []
        for prop_name_raw, raw_prop_def in properties.items():
            prop_def = self._resolve_schema(_as_dict(raw_prop_def))
            ftype = self._map_field_type(prop_def.get("type", "string"))
            desc_raw = prop_def.get("description")
            desc = str(desc_raw) if desc_raw is not None else None
            example: Any = prop_def.get("example")
            min_len = prop_def.get("minLength")
            max_len = prop_def.get("maxLength")

            prop_name = str(prop_name_raw)
            fields.append(
                BodyField(
                    name=prop_name,
                    type=ftype,
                    example=example,
                    required=prop_name in required_set,
                    description=desc,
                    min_length=int(min_len) if isinstance(min_len, int) else None,
                    max_length=int(max_len) if isinstance(max_len, int) else None,
                )
            )

        return fields

    def _parse_responses(self, raw_responses: Dict[str, Any]) -> EndpointResponses:
        success: Optional[ResponseSuccess] = None
        errors: List[ResponseError] = []

        for code_str_raw, raw_resp in raw_responses.items():
            resp_dict = self._resolve_schema(_as_dict(raw_resp))
            desc = str(resp_dict.get("description") or "")
            example: Any = None

            content = _as_dict(resp_dict.get("content"))
            if content:
                app_json = _as_dict(content.get("application/json"))
                if app_json:
                    example = app_json.get("example")
                    if example is None and "schema" in app_json:
                        s = self._resolve_schema(_as_dict(app_json.get("schema")))
                        example = s.get("example")

            if example is None:
                example = resp_dict.get("example")

            code_str = str(code_str_raw)
            status_code: Optional[int] = int(code_str) if code_str.isdigit() else None

            if status_code is not None:
                if 200 <= status_code < 300:
                    if success is None:
                        success = ResponseSuccess(
                            status=status_code,
                            description=desc or "Success",
                            example=example,
                        )
                elif 400 <= status_code < 600:
                    errors.append(
                        ResponseError(
                            status=status_code,
                            message=desc or f"HTTP {status_code} Error",
                            description=desc,
                            example=example,
                        )
                    )
            elif code_str.lower() == "default":
                if success is None:
                    success = ResponseSuccess(status=200, description=desc or "Success", example=example)

        if success is None:
            success = ResponseSuccess(status=200, description="Success")

        return EndpointResponses(success=success, errors=errors)
