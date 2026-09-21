import json
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

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

SUPPORTED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}


def _as_dict(val: Any) -> Dict[str, Any]:
    if isinstance(val, dict):
        return cast(Dict[str, Any], val)
    return {}


def _as_list(val: Any) -> List[Any]:
    if isinstance(val, list):
        return cast(List[Any], val)
    return []


def _infer_field_type(val: Any) -> FieldType:
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "number"
    if isinstance(val, list):
        return "array"
    if isinstance(val, dict):
        return "object"
    return "string"


class PostmanCollectionDriver(TeraDriver):
    """
    Driver capable of ingesting Postman Collections across multiple versions:
    - v1.0.0 (legacy collections with root 'requests' and 'folders')
    - v2.0.0 (schema collection/v2.0.0)
    - v2.1.0 (schema collection/v2.1.0)
    - v3.x / Draft 07 (modern workspace schemas)
    """

    def __init__(self, source: Union[Path, str, Dict[str, Any]]) -> None:
        self.source = source
        self.raw_data: Dict[str, Any] = {}

    def _load_raw_data(self) -> Dict[str, Any]:
        if isinstance(self.source, dict):
            return self.source

        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"Postman collection file '{path}' not found.")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            raise TeraError("File Read Error", f"Could not read '{path}': {e}")

        try:
            data: Any = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("Root must be a JSON object.")
            return cast(Dict[str, Any], data)
        except Exception as e:
            raise TeraError("Postman JSON Error", f"Invalid Postman JSON in '{path}': {e}")

    def load(self) -> TeraSchema:
        self.raw_data = self._load_raw_data()

        # Check format version
        if "requests" in self.raw_data and "info" not in self.raw_data:
            return self._parse_v1()
        return self._parse_v2_or_v3()

    def _normalize_path(self, raw_url: Union[str, Dict[str, Any]]) -> Tuple[str, List[str], Dict[str, str]]:
        """
        Normalizes a Postman URL into:
        (canonical_openapi_path, path_params_names, query_params_dict)
        """
        path_str = ""
        query_dict: Dict[str, str] = {}

        if isinstance(raw_url, dict):
            raw_url_dict = _as_dict(raw_url)
            # Object URL (v2.0, v2.1, v3)
            path_segments: List[str] = []
            if "path" in raw_url_dict and isinstance(raw_url_dict["path"], list):
                raw_path_list = _as_list(raw_url_dict["path"])
                path_segments = [str(p) for p in raw_path_list if p]
                path_str = "/" + "/".join(path_segments)
            elif "raw" in raw_url_dict:
                path_str = self._clean_url_string(str(raw_url_dict.get("raw") or ""))

            if "query" in raw_url_dict and isinstance(raw_url_dict["query"], list):
                for q in _as_list(raw_url_dict["query"]):
                    if isinstance(q, dict):
                        q_dict = _as_dict(q)
                        key = q_dict.get("key")
                        if key:
                            query_dict[str(key)] = str(q_dict.get("value") or "")
        else:
            path_str = self._clean_url_string(str(raw_url))
            parsed = urllib.parse.urlparse(str(raw_url))
            if parsed.query:
                parsed_q = urllib.parse.parse_qs(parsed.query)
                for k, v in parsed_q.items():
                    query_dict[k] = v[0] if v else ""

        # Normalize :param to {param} and {{param}} to {param}
        path_str = re.sub(r":([a-zA-Z0-9_]+)", r"{\1}", path_str)
        path_str = re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", r"{\1}", path_str)

        if not path_str.startswith("/"):
            path_str = "/" + path_str

        # Extract path parameters
        path_params = re.findall(r"\{([a-zA-Z0-9_]+)\}", path_str)

        return path_str, path_params, query_dict

    def _clean_url_string(self, url_str: str) -> str:
        # Remove query params
        url_without_query = url_str.split("?", 1)[0]
        # Remove scheme and domain if present
        if "://" in url_without_query:
            parsed = urllib.parse.urlparse(url_without_query)
            return parsed.path or "/"
        # Remove leading variable prefixes like {{base_url}}
        cleaned = re.sub(r"^\{\{[^}]+\}\}", "", url_without_query)
        return cleaned if cleaned.startswith("/") else "/" + cleaned

    def _extract_body_fields(self, body_data: Optional[Dict[str, Any]]) -> List[BodyField]:
        if not body_data:
            return []

        body_dict = _as_dict(body_data)
        mode = body_dict.get("mode")
        fields: List[BodyField] = []

        if mode == "raw":
            raw_text = body_dict.get("raw")
            if isinstance(raw_text, str) and raw_text.strip():
                try:
                    parsed: Any = json.loads(raw_text)
                    if isinstance(parsed, dict):
                        for k, v in _as_dict(parsed).items():
                            fields.append(
                                BodyField(
                                    name=str(k),
                                    type=_infer_field_type(v),
                                    required=True,
                                    example=v,
                                )
                            )
                except Exception:
                    pass

        elif mode in ("urlencoded", "formdata"):
            items = _as_list(body_dict.get(mode))
            for item in items:
                if isinstance(item, dict):
                    item_dict = _as_dict(item)
                    key = item_dict.get("key")
                    if key:
                        desc = item_dict.get("description")
                        fields.append(
                            BodyField(
                                name=str(key),
                                type="string",
                                required=not bool(item_dict.get("disabled")),
                                description=str(desc) if desc is not None else None,
                                example=item_dict.get("value"),
                            )
                        )

        return fields

    def _extract_responses(self, responses_list: Optional[List[Any]]) -> EndpointResponses:
        success_resp: Optional[ResponseSuccess] = None
        error_resps: List[ResponseError] = []

        if responses_list:
            for resp in _as_list(responses_list):
                if not isinstance(resp, dict):
                    continue

                resp_dict = _as_dict(resp)
                code = resp_dict.get("code")
                # Fallback for v1 responses format
                if code is None and isinstance(resp_dict.get("responseCode"), dict):
                    resp_code_dict = _as_dict(resp_dict.get("responseCode"))
                    code = resp_code_dict.get("code")

                if not isinstance(code, int):
                    continue

                status_text = str(resp_dict.get("status") or "")
                body_text = resp_dict.get("body") or resp_dict.get("text")
                example_val: Any = None
                if isinstance(body_text, str) and body_text.strip():
                    try:
                        example_val = json.loads(body_text)
                    except Exception:
                        example_val = body_text

                if 200 <= code < 400:
                    if success_resp is None or code == 200:
                        success_resp = ResponseSuccess(
                            status=code,
                            description=status_text or "Success",
                            example=example_val,
                        )
                elif 400 <= code < 600:
                    error_resps.append(
                        ResponseError(
                            status=code,
                            message=status_text or f"HTTP {code}",
                            description=status_text,
                            example=example_val,
                        )
                    )

        if success_resp is None:
            success_resp = ResponseSuccess(status=200, description="Success")

        return EndpointResponses(success=success_resp, errors=error_resps)

    def _detect_auth(self, request_data: Dict[str, Any], global_auth: Optional[Dict[str, Any]]) -> bool:
        req_auth = request_data.get("auth")
        if req_auth and isinstance(req_auth, dict):
            req_auth_dict = _as_dict(req_auth)
            if req_auth_dict.get("type") != "noauth":
                return True
        if global_auth:
            if global_auth.get("type") != "noauth":
                return True

        headers = request_data.get("header") or request_data.get("headers")
        if isinstance(headers, list):
            for h in _as_list(headers):
                if isinstance(h, dict):
                    h_dict = _as_dict(h)
                    if str(h_dict.get("key", "")).lower() == "authorization":
                        return True
        elif isinstance(headers, str):
            if "authorization:" in headers.lower():
                return True

        return False

    def _parse_global_auth(self, auth_dict: Optional[Dict[str, Any]]) -> Optional[AuthConfig]:
        if not auth_dict:
            return None
        auth_data = _as_dict(auth_dict)
        auth_type = str(auth_data.get("type", "")).lower()
        if auth_type == "bearer":
            return AuthConfig(type=cast(AuthType, "bearer"))
        if auth_type == "basic":
            return AuthConfig(type=cast(AuthType, "basic"))
        if auth_type in ("apikey", "api_key"):
            return AuthConfig(type=cast(AuthType, "apikey"))
        return None

    def _parse_v1(self) -> TeraSchema:
        name = str(self.raw_data.get("name") or "Imported Postman Collection")
        raw_desc = self.raw_data.get("description")
        description: Optional[str] = str(raw_desc) if raw_desc is not None else None

        # Map folders to request IDs for tagging
        folder_tag_map: Dict[str, str] = {}
        folders = _as_list(self.raw_data.get("folders"))
        for f in folders:
            if isinstance(f, dict):
                f_dict = _as_dict(f)
                fname = str(f_dict.get("name", ""))
                order_list = _as_list(f_dict.get("order"))
                for rid in order_list:
                    folder_tag_map[str(rid)] = fname

        endpoints: List[Endpoint] = []
        requests = _as_list(self.raw_data.get("requests"))

        for req in requests:
            if not isinstance(req, dict):
                continue
            req_dict = _as_dict(req)

            method_str = str(req_dict.get("method", "GET")).upper()
            if method_str not in SUPPORTED_METHODS:
                continue
            method = cast(HTTPMethod, method_str)

            raw_url_val = req_dict.get("url")
            raw_url: Union[str, Dict[str, Any]]
            if isinstance(raw_url_val, (str, dict)):
                raw_url = cast(Union[str, Dict[str, Any]], raw_url_val)
            else:
                raw_url = "/"
            path, path_param_names, query_params = self._normalize_path(raw_url)

            path_fields = [
                ParamField(name=p, type="string", required=True)
                for p in path_param_names
            ]
            query_fields = [
                ParamField(name=k, type="string", required=False, example=v)
                for k, v in query_params.items()
            ]

            # Body
            body_fields: List[BodyField] = []
            data_mode = req_dict.get("dataMode")
            if data_mode == "raw" and "rawModeData" in req_dict:
                body_fields = self._extract_body_fields({"mode": "raw", "raw": req_dict.get("rawModeData")})
            elif "data" in req_dict and isinstance(req_dict["data"], list):
                body_fields = self._extract_body_fields({"mode": "formdata", "formdata": req_dict.get("data")})

            responses = self._extract_responses(_as_list(req_dict.get("responses")))
            auth_required = self._detect_auth(req_dict, None)
            tag = folder_tag_map.get(str(req_dict.get("id")))
            req_desc = req_dict.get("description")

            endpoints.append(
                Endpoint(
                    path=path,
                    method=method,
                    summary=str(req_dict.get("name") or f"{method} {path}"),
                    description=str(req_desc) if req_desc is not None else None,
                    tag=tag,
                    auth_required=auth_required,
                    params=EndpointParams(path=path_fields, query=query_fields)
                    if (path_fields or query_fields)
                    else None,
                    body=body_fields,
                    responses=responses,
                )
            )

        return TeraSchema(
            api=ApiConfig(
                name=name,
                version="1.0.0",
                description=description,
            ),
            endpoints=endpoints,
        )

    def _parse_v2_or_v3(self) -> TeraSchema:
        info = _as_dict(self.raw_data.get("info"))
        name = str(info.get("name") or "Imported Postman Collection")
        raw_desc = info.get("description")
        description: Optional[str] = str(raw_desc) if raw_desc is not None else None
        global_auth = _as_dict(self.raw_data.get("auth")) if isinstance(self.raw_data.get("auth"), dict) else None
        auth_config = self._parse_global_auth(global_auth)

        endpoints: List[Endpoint] = []

        def traverse_items(items: List[Any], current_hierarchy: List[str]) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_dict = _as_dict(item)

                item_name = str(item_dict.get("name", ""))

                # Folder node
                if "item" in item_dict and isinstance(item_dict["item"], list):
                    next_hierarchy = current_hierarchy + [item_name]
                    traverse_items(_as_list(item_dict["item"]), next_hierarchy)
                    continue

                # Request node
                if "request" not in item_dict:
                    continue

                raw_req = item_dict["request"]
                req_data: Dict[str, Any]
                if isinstance(raw_req, str):
                    # Plain URL request
                    req_data = {"method": "GET", "url": raw_req}
                elif isinstance(raw_req, dict):
                    req_data = _as_dict(raw_req)
                else:
                    continue

                method_str = str(req_data.get("method", "GET")).upper()
                if method_str not in SUPPORTED_METHODS:
                    continue
                method = cast(HTTPMethod, method_str)

                raw_url_val = req_data.get("url")
                raw_url: Union[str, Dict[str, Any]]
                if isinstance(raw_url_val, (str, dict)):
                    raw_url = cast(Union[str, Dict[str, Any]], raw_url_val)
                else:
                    raw_url = "/"
                path, path_param_names, query_params = self._normalize_path(raw_url)

                path_fields = [
                    ParamField(name=p, type="string", required=True)
                    for p in path_param_names
                ]
                query_fields = [
                    ParamField(name=k, type="string", required=False, example=v)
                    for k, v in query_params.items()
                ]

                raw_body = req_data.get("body")
                body_dict = _as_dict(raw_body) if isinstance(raw_body, dict) else None
                body_fields = self._extract_body_fields(body_dict)
                responses = self._extract_responses(_as_list(item_dict.get("response")))
                auth_required = self._detect_auth(req_data, global_auth)

                tag = current_hierarchy[0] if current_hierarchy else None
                endpoint_desc = req_data.get("description") or item_dict.get("description")

                endpoints.append(
                    Endpoint(
                        path=path,
                        method=method,
                        summary=item_name or f"{method} {path}",
                        description=str(endpoint_desc) if endpoint_desc is not None else None,
                        tag=tag,
                        auth_required=auth_required,
                        params=EndpointParams(path=path_fields, query=query_fields)
                        if (path_fields or query_fields)
                        else None,
                        body=body_fields,
                        responses=responses,
                    )
                )

        root_items = _as_list(self.raw_data.get("item"))
        traverse_items(root_items, [])

        return TeraSchema(
            api=ApiConfig(
                name=name,
                version="1.0.0",
                description=description,
                auth=auth_config,
            ),
            endpoints=endpoints,
        )
