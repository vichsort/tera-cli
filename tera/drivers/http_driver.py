import json
import os
import urllib.error
import urllib.request
import yaml
from typing import Any, Dict, Optional, cast
from tera.contracts import TeraDriver
from tera.domain import TeraSchema
from tera.drivers.openapi_driver import OpenApiDriver
from tera.exceptions import TeraError


class HttpDriver(TeraDriver):
    """
    Driver capable of fetching API specifications from remote HTTP/HTTPS endpoints.
    Automatically detects OpenAPI (JSON/YAML) or canonical Tera IR specifications.
    Supports custom headers and environment variable token injection.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> None:
        self.url = url
        self.headers: Dict[str, str] = dict(headers) if headers else {}
        self.timeout = timeout

    def _prepare_headers(self) -> Dict[str, str]:
        hdrs = {
            "User-Agent": "tera-cli/0.1.0",
            "Accept": "application/json, application/yaml, application/x-yaml, text/yaml, text/plain, */*",
        }
        hdrs.update(self.headers)

        # Check environment variable for authorization fallback if not already specified
        if "Authorization" not in hdrs and "TERA_HTTP_AUTH" in os.environ:
            auth_val = os.environ["TERA_HTTP_AUTH"].strip()
            if auth_val:
                hdrs["Authorization"] = auth_val

        return hdrs

    def _fetch_content(self) -> str:
        headers = self._prepare_headers()
        req = urllib.request.Request(self.url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                raw_bytes: bytes = resp.read()
                return raw_bytes.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            raise TeraError(
                "HTTP Error",
                f"HTTP request to '{self.url}' failed with status {e.code}: {e.reason}",
            )
        except urllib.error.URLError as e:
            raise TeraError(
                "Network Error",
                f"Failed to reach '{self.url}': {e.reason}",
            )
        except TimeoutError:
            raise TeraError(
                "Timeout Error",
                f"Request to '{self.url}' timed out after {self.timeout}s.",
            )
        except Exception as e:
            raise TeraError(
                "Fetch Error",
                f"Unexpected error fetching '{self.url}': {e}",
            )

    def load(self) -> TeraSchema:
        content = self._fetch_content()
        if not content.strip():
            raise TeraError("Empty Response", f"Received empty response from '{self.url}'.")

        data: Optional[Dict[str, Any]] = None

        # 1. Try parsing as JSON first
        try:
            parsed_json: Any = json.loads(content)
            if isinstance(parsed_json, dict):
                data = cast(Dict[str, Any], parsed_json)
        except Exception:
            pass

        # 2. Try parsing as YAML if not JSON
        if data is None:
            try:
                parsed_yaml: Any = yaml.safe_load(content)
                if isinstance(parsed_yaml, dict):
                    data = cast(Dict[str, Any], parsed_yaml)
            except Exception as e:
                raise TeraError(
                    "Parsing Error",
                    f"Could not parse payload from '{self.url}' as JSON or YAML: {e}",
                )

        if data is None:
            raise TeraError(
                "Invalid Payload",
                f"Payload from '{self.url}' is not a valid JSON or YAML object mapping.",
            )

        # 3. Detect specification format: OpenAPI vs Canonical Tera
        is_openapi = (
            "openapi" in data
            or "swagger" in data
            or (isinstance(data.get("openapi"), str))
            or (isinstance(data.get("swagger"), str))
        )

        if is_openapi:
            driver = OpenApiDriver(data)
            return driver.load()

        # Fallback to canonical TeraSchema
        try:
            return TeraSchema.model_validate(data)
        except Exception as e:
            raise TeraError(
                "Schema Validation Error",
                f"Remote data from '{self.url}' could not be validated as TeraSchema or OpenAPI: {e}",
            )

