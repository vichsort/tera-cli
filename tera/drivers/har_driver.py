import json
import re
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

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

SUPPORTED_METHODS: Set[str] = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
COMMON_PREFIXES: Set[str] = {"api", "v1", "v2", "v3", "v4", "rest", "services"}


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


def _is_dynamic_segment(seg: str) -> bool:
    if re.match(r"^\d+$", seg):
        return True
    if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", seg):
        return True
    if re.match(r"^[0-9a-fA-F]{24}$", seg) or re.match(r"^[0-9a-fA-F]{32}$", seg):
        return True
    if re.match(r"^\{[a-zA-Z0-9_]+\}$", seg) or re.match(r"^:[a-zA-Z0-9_]+$", seg):
        return True
    return False


def _is_slug_or_id(seg: str) -> bool:
    if _is_dynamic_segment(seg):
        return True
    if re.match(r"^[0-9a-zA-Z_-]+$", seg) and (any(c.isdigit() for c in seg) or "-" in seg or "_" in seg):
        return True
    return False


def _derive_param_name(seg: str, prev_seg: Optional[str], used_names: Set[str]) -> str:
    m_bracket = re.match(r"^\{([a-zA-Z0-9_]+)\}$", seg)
    if m_bracket:
        base_name = m_bracket.group(1)
    else:
        m_colon = re.match(r"^:([a-zA-Z0-9_]+)$", seg)
        if m_colon:
            base_name = m_colon.group(1)
        elif prev_seg:
            p = prev_seg.lower()
            if p.endswith("ies") and len(p) > 3:
                singular = p[:-3] + "y"
            elif p.endswith("ses") and len(p) > 3:
                singular = p[:-2]
            elif p.endswith("s") and not p.endswith("ss") and len(p) > 1:
                singular = p[:-1]
            else:
                singular = p
            base_name = f"{singular}_id"
        else:
            base_name = "id"

    name = base_name
    counter = 2
    while name in used_names:
        name = f"{base_name}_{counter}"
        counter += 1
    used_names.add(name)
    return name


class _EntryRecord:
    entry_idx: int
    method: HTTPMethod
    raw_url: str
    base_url: str
    raw_path: str
    segments: List[str]
    query_dict: Dict[str, str]
    post_data: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    headers: List[Dict[str, Any]]
    comment: Optional[str]
    canonical_path: str
    path_param_names: List[str]

    def __init__(
        self,
        entry_idx: int,
        method: HTTPMethod,
        raw_url: str,
        base_url: str,
        raw_path: str,
        segments: List[str],
        query_dict: Dict[str, str],
        post_data: Optional[Dict[str, Any]],
        response_data: Optional[Dict[str, Any]],
        headers: List[Dict[str, Any]],
        comment: Optional[str],
    ) -> None:
        self.entry_idx = entry_idx
        self.method = method
        self.raw_url = raw_url
        self.base_url = base_url
        self.raw_path = raw_path
        self.segments = segments
        self.query_dict = query_dict
        self.post_data = post_data
        self.response_data = response_data
        self.headers = headers
        self.comment = comment

        self.canonical_path = ""
        self.path_param_names = []


class HarDriver(TeraDriver):
    """
    Input driver that parses HTTP Archive (.har) files and reverse-engineers
    a canonical TeraSchema specification with heuristic dynamic route collapse,
    payload inference, and response aggregation.
    """

    def __init__(self, source: Union[Path, str, Dict[str, Any]]) -> None:
        self.source = source
        self.raw_data: Dict[str, Any] = {}

    def _load_raw_data(self) -> Dict[str, Any]:
        if isinstance(self.source, dict):
            return self.source

        path = Path(self.source)
        if not path.exists():
            raise FileNotFoundError(f"HAR file '{path}' not found.")

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
            raise TeraError("HAR JSON Error", f"Invalid HAR JSON in '{path}': {e}")

    def load(self) -> TeraSchema:
        self.raw_data = self._load_raw_data()
        log_data = _as_dict(self.raw_data.get("log"))
        if not log_data and "log" not in self.raw_data:
            raise TeraError("HAR Format Error", "Invalid HAR structure: missing 'log' root object.")

        creator_info = _as_dict(log_data.get("creator"))
        creator_name = str(creator_info.get("name") or "HTTP Archive")

        entries = _as_list(log_data.get("entries"))
        return self._build_schema(entries, creator_name)

    def _build_schema(self, entries: List[Any], creator_name: str) -> TeraSchema:
        records: List[_EntryRecord] = []
        base_urls: List[str] = []
        auth_types: List[AuthType] = []

        for idx, item in enumerate(entries):
            if not isinstance(item, dict):
                continue
            item_dict = _as_dict(item)
            request = _as_dict(item_dict.get("request"))
            response = _as_dict(item_dict.get("response"))
            if not request:
                continue

            method_str = str(request.get("method", "GET")).upper()
            if method_str not in SUPPORTED_METHODS:
                continue
            method = cast(HTTPMethod, method_str)

            raw_url = str(request.get("url") or "/")
            parsed_url = urllib.parse.urlparse(raw_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.scheme and parsed_url.netloc else ""
            if base_url:
                base_urls.append(base_url)

            raw_path = parsed_url.path or "/"
            raw_path = re.sub(r"/+", "/", raw_path)
            segments = [s for s in raw_path.strip("/").split("/") if s]

            # Query params
            query_dict: Dict[str, str] = {}
            for q in _as_list(request.get("queryString")):
                if isinstance(q, dict):
                    q_dict = _as_dict(q)
                    q_name = str(q_dict.get("name") or "")
                    if q_name:
                        query_dict[q_name] = str(q_dict.get("value") or "")
            if parsed_url.query and not query_dict:
                parsed_qs = urllib.parse.parse_qs(parsed_url.query)
                for k, v_list in parsed_qs.items():
                    query_dict[k] = v_list[0] if v_list else ""

            # Headers
            headers: List[Dict[str, Any]] = []
            for h in _as_list(request.get("headers")):
                if isinstance(h, dict):
                    h_dict = _as_dict(h)
                    headers.append(h_dict)
                    h_name = str(h_dict.get("name") or "").lower()
                    h_val = str(h_dict.get("value") or "")
                    if h_name == "authorization":
                        if h_val.lower().startswith("bearer "):
                            auth_types.append("bearer")
                        elif h_val.lower().startswith("basic "):
                            auth_types.append("basic")
                    elif h_name in ("x-api-key", "api-key", "apikey"):
                        auth_types.append("apikey")

            post_data = _as_dict(request.get("postData")) if isinstance(request.get("postData"), dict) else None
            comment = str(item_dict.get("comment")) if item_dict.get("comment") else None

            records.append(
                _EntryRecord(
                    entry_idx=idx,
                    method=method,
                    raw_url=raw_url,
                    base_url=base_url,
                    raw_path=raw_path,
                    segments=segments,
                    query_dict=query_dict,
                    post_data=post_data,
                    response_data=response if response else None,
                    headers=headers,
                    comment=comment,
                )
            )

        if not records:
            api_name = f"HAR Capture ({creator_name})" if creator_name != "HTTP Archive" else "Imported HAR Capture"
            return TeraSchema(api=ApiConfig(name=api_name, version="1.0.0"), endpoints=[])

        # Dynamic route collapse
        self._collapse_routes(records)

        # Aggregate endpoints
        grouped_records: Dict[Tuple[HTTPMethod, str], List[_EntryRecord]] = defaultdict(list)
        for rec in records:
            grouped_records[(rec.method, rec.canonical_path)].append(rec)

        endpoints: List[Endpoint] = []
        for (method, canonical_path), group_records in grouped_records.items():
            first_rec = group_records[0]

            path_fields = [
                ParamField(name=p, type="string", required=True)
                for p in first_rec.path_param_names
            ]

            # Aggregate query params
            merged_query: Dict[str, str] = {}
            for r in group_records:
                for qk, qv in r.query_dict.items():
                    if qk not in merged_query or (not merged_query[qk] and qv):
                        merged_query[qk] = qv

            query_fields = [
                ParamField(name=k, type="string", required=False, example=v if v else None)
                for k, v in merged_query.items()
            ]

            params: Optional[EndpointParams] = None
            if path_fields or query_fields:
                params = EndpointParams(path=path_fields, query=query_fields)

            # Aggregate body fields
            body_fields = self._aggregate_body_fields(group_records)

            # Aggregate responses
            responses = self._aggregate_responses(group_records)

            # Detect auth
            auth_required = any(self._is_auth_header_present(r.headers) for r in group_records)

            # Derive tag
            tag = self._derive_tag(canonical_path)

            endpoints.append(
                Endpoint(
                    path=canonical_path,
                    method=method,
                    summary=f"{method} {canonical_path}",
                    description=first_rec.comment,
                    tag=tag,
                    auth_required=auth_required,
                    params=params,
                    body=body_fields,
                    responses=responses,
                )
            )

        # Base URL detection
        most_common_base = Counter(base_urls).most_common(1)
        base_url_val = most_common_base[0][0] if most_common_base else "/"

        # Auth detection
        auth_config: Optional[AuthConfig] = None
        if auth_types:
            most_common_auth = Counter(auth_types).most_common(1)
            auth_config = AuthConfig(type=most_common_auth[0][0])

        api_name = f"HAR Capture ({creator_name})" if creator_name != "HTTP Archive" else "Imported HAR Capture"
        return TeraSchema(
            api=ApiConfig(
                name=api_name,
                version="1.0.0",
                description=f"Reverse-engineered specification from HTTP Archive generated by {creator_name}.",
                base_url=base_url_val,
                auth=auth_config,
            ),
            endpoints=endpoints,
        )

    def _collapse_routes(self, records: List[_EntryRecord]) -> None:
        dynamic_positions: Set[Tuple[int, int]] = set()

        # Pass 1: regex heuristics per segment
        for rec in records:
            for i, seg in enumerate(rec.segments):
                if _is_dynamic_segment(seg):
                    dynamic_positions.add((rec.entry_idx, i))

        # Pass 2: multi-entry divergence clustering
        by_method_and_len: Dict[Tuple[str, int], List[_EntryRecord]] = defaultdict(list)
        for rec in records:
            by_method_and_len[(rec.method, len(rec.segments))].append(rec)

        for _, group in by_method_and_len.items():
            if len(group) < 2:
                continue
            seg_len = len(group[0].segments)
            for i in range(seg_len):
                prefix_map: Dict[Tuple[str, ...], List[_EntryRecord]] = defaultdict(list)
                for rec in group:
                    prefix = tuple(rec.segments[:i])
                    prefix_map[prefix].append(rec)

                for _, sub_group in prefix_map.items():
                    if len(sub_group) < 2:
                        continue
                    distinct_values = {r.segments[i] for r in sub_group}
                    if len(distinct_values) >= 2:
                        prev_seg = sub_group[0].segments[i - 1] if i > 0 else None
                        is_plural = bool(
                            prev_seg
                            and prev_seg.lower().endswith("s")
                            and not prev_seg.lower().endswith("ss")
                        )
                        if is_plural or any(_is_slug_or_id(v) for v in distinct_values):
                            for r in sub_group:
                                dynamic_positions.add((r.entry_idx, i))

        # Pass 3: construct canonical paths and path parameter names
        for rec in records:
            used_param_names: Set[str] = set()
            canonical_segs: List[str] = []
            param_names: List[str] = []

            for i, seg in enumerate(rec.segments):
                prev_seg = rec.segments[i - 1] if i > 0 else None
                if (rec.entry_idx, i) in dynamic_positions:
                    pname = _derive_param_name(seg, prev_seg, used_param_names)
                    canonical_segs.append(f"{{{pname}}}")
                    param_names.append(pname)
                else:
                    canonical_segs.append(seg)

            rec.canonical_path = "/" + "/".join(canonical_segs) if canonical_segs else "/"
            rec.path_param_names = param_names

    def _aggregate_body_fields(self, group_records: List[_EntryRecord]) -> List[BodyField]:
        records_with_body = [r for r in group_records if r.post_data]
        if not records_with_body:
            return []

        field_occurrences: Dict[str, int] = defaultdict(int)
        field_types: Dict[str, FieldType] = {}
        field_examples: Dict[str, Any] = {}

        total_bodies = len(records_with_body)

        for rec in records_with_body:
            post_data = _as_dict(rec.post_data)
            mime = str(post_data.get("mimeType") or "").lower()

            if "json" in mime:
                raw_text = post_data.get("text")
                if isinstance(raw_text, str) and raw_text.strip():
                    try:
                        parsed: Any = json.loads(raw_text)
                        if isinstance(parsed, dict):
                            for k, v in _as_dict(parsed).items():
                                field_name = str(k)
                                field_occurrences[field_name] += 1
                                if field_name not in field_types:
                                    field_types[field_name] = _infer_field_type(v)
                                    field_examples[field_name] = v
                    except Exception:
                        pass
            elif "urlencoded" in mime or "form-data" in mime or "form" in mime:
                params = _as_list(post_data.get("params"))
                for p in params:
                    if isinstance(p, dict):
                        p_dict = _as_dict(p)
                        p_name = str(p_dict.get("name") or "")
                        if p_name:
                            field_occurrences[p_name] += 1
                            if p_name not in field_types:
                                field_types[p_name] = "string"
                                field_examples[p_name] = p_dict.get("value")

        fields: List[BodyField] = []
        for name, count in field_occurrences.items():
            fields.append(
                BodyField(
                    name=name,
                    type=field_types.get(name, "string"),
                    required=(count == total_bodies),
                    example=field_examples.get(name),
                )
            )

        return fields

    def _aggregate_responses(self, group_records: List[_EntryRecord]) -> EndpointResponses:
        success_resp: Optional[ResponseSuccess] = None
        error_resps_map: Dict[int, ResponseError] = {}

        for rec in group_records:
            if not rec.response_data:
                continue

            resp_dict = _as_dict(rec.response_data)
            status_val = resp_dict.get("status")
            if not isinstance(status_val, int):
                continue

            status_text = str(resp_dict.get("statusText") or "")
            content = _as_dict(resp_dict.get("content"))
            body_text = content.get("text")
            example_val: Any = None
            if isinstance(body_text, str) and body_text.strip():
                try:
                    example_val = json.loads(body_text)
                except Exception:
                    example_val = body_text

            if 200 <= status_val < 400:
                if success_resp is None or status_val == 200:
                    success_resp = ResponseSuccess(
                        status=status_val,
                        description=status_text or "Success",
                        example=example_val,
                    )
            elif 400 <= status_val < 600:
                if status_val not in error_resps_map:
                    error_resps_map[status_val] = ResponseError(
                        status=status_val,
                        message=status_text or f"HTTP {status_val}",
                        description=status_text or f"HTTP {status_val}",
                        example=example_val,
                    )

        if success_resp is None:
            success_resp = ResponseSuccess(status=200, description="Success")

        sorted_errors = [error_resps_map[k] for k in sorted(error_resps_map.keys())]
        return EndpointResponses(success=success_resp, errors=sorted_errors)

    def _is_auth_header_present(self, headers: List[Dict[str, Any]]) -> bool:
        for h in headers:
            name = str(h.get("name") or "").lower()
            if name in ("authorization", "x-api-key", "api-key", "apikey"):
                return True
        return False

    def _derive_tag(self, canonical_path: str) -> Optional[str]:
        segments = [s for s in canonical_path.strip("/").split("/") if s]
        for seg in segments:
            seg_lower = seg.lower()
            if seg_lower not in COMMON_PREFIXES and not seg.startswith("{"):
                return seg
        return None
