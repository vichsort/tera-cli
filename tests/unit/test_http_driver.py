import io
import os
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch
import pytest
from tera.core import factory
from tera.drivers import HttpDriver
from tera.exceptions import TeraError


def _make_mock_response(content: str, charset: str = "utf-8", status: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.read.return_value = content.encode(charset)
    mock_resp.headers.get_content_charset.return_value = charset
    mock_resp.status = status
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


def test_http_driver_loads_openapi_json() -> None:
    sample_json = (
        '{"openapi": "3.0.0", "info": {"title": "Remote API", "version": "1.0.0"}, '
        '"paths": {"/ping": {"get": {"responses": {"200": {"description": "pong"}}}}}}'
    )

    with patch("urllib.request.urlopen", return_value=_make_mock_response(sample_json)):
        driver = HttpDriver("https://api.example.com/openapi.json")
        schema = driver.load()

    assert schema.api.name == "Remote API"
    assert schema.api.version == "1.0.0"
    assert len(schema.endpoints) == 1
    assert schema.endpoints[0].path == "/ping"


def test_http_driver_loads_openapi_yaml() -> None:
    sample_yaml = """
openapi: 3.0.0
info:
  title: Remote YAML API
  version: 2.1.0
paths:
  /health:
    get:
      summary: Health check
      responses:
        '200':
          description: OK
"""

    with patch("urllib.request.urlopen", return_value=_make_mock_response(sample_yaml)):
        driver = HttpDriver("http://localhost:8080/openapi.yaml")
        schema = driver.load()

    assert schema.api.name == "Remote YAML API"
    assert schema.api.version == "2.1.0"
    assert len(schema.endpoints) == 1
    assert schema.endpoints[0].path == "/health"


def test_http_driver_loads_canonical_tera_yaml() -> None:
    sample_tera_yaml = """
api:
  name: Canonical Remote API
  version: 3.0.0
endpoints:
  - path: /users
    method: GET
    summary: List users
    responses:
      success:
        status: 200
        description: OK
"""

    with patch("urllib.request.urlopen", return_value=_make_mock_response(sample_tera_yaml)):
        driver = HttpDriver("https://cdn.example.com/docs.yaml")
        schema = driver.load()

    assert schema.api.name == "Canonical Remote API"
    assert schema.api.version == "3.0.0"
    assert len(schema.endpoints) == 1
    assert schema.endpoints[0].path == "/users"


def test_http_driver_auto_detection_in_factory() -> None:
    sample_json = '{"openapi": "3.0.0", "info": {"title": "Auto API", "version": "1.0.0"}, "paths": {}}'

    with patch("urllib.request.urlopen", return_value=_make_mock_response(sample_json)):
        driver = factory.get_driver("https://api.test.com/spec")
        assert isinstance(driver, HttpDriver)
        schema = driver.load()
        assert schema.api.name == "Auto API"


def test_http_driver_headers_and_auth_env() -> None:
    sample_json = '{"openapi": "3.0.0", "info": {"title": "Auth API", "version": "1.0.0"}, "paths": {}}'

    captured_requests: list[urllib.request.Request] = []

    def mock_urlopen(req: urllib.request.Request, timeout: float = 10.0) -> MagicMock:
        captured_requests.append(req)
        return _make_mock_response(sample_json)

    # 1. With explicit custom header
    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        driver = HttpDriver("https://api.example.com", headers={"X-Custom-Token": "secret123"})
        driver.load()

    assert len(captured_requests) == 1
    req1 = captured_requests[0]
    assert req1.get_header("X-custom-token") == "secret123"

    # 2. With TERA_HTTP_AUTH environment variable
    captured_requests.clear()
    with patch.dict(os.environ, {"TERA_HTTP_AUTH": "Bearer env-token-456"}):
        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            driver2 = HttpDriver("https://api.example.com")
            driver2.load()

    assert len(captured_requests) == 1
    req2 = captured_requests[0]
    assert req2.get_header("Authorization") == "Bearer env-token-456"

    # 3. Explicit Authorization takes precedence over TERA_HTTP_AUTH
    captured_requests.clear()
    with patch.dict(os.environ, {"TERA_HTTP_AUTH": "Bearer env-token-456"}):
        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            driver3 = HttpDriver("https://api.example.com", headers={"Authorization": "Bearer explicit-token"})
            driver3.load()

    assert len(captured_requests) == 1
    req3 = captured_requests[0]
    assert req3.get_header("Authorization") == "Bearer explicit-token"


def test_http_driver_http_error_handling() -> None:
    err = urllib.error.HTTPError(
        url="https://api.example.com/404",
        code=404,
        msg="Not Found",
        hdrs=MagicMock(),
        fp=io.BytesIO(b"Not Found"),
    )

    with patch("urllib.request.urlopen", side_effect=err):
        driver = HttpDriver("https://api.example.com/404")
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "HTTP Error" in str(exc.value)
        assert "404" in str(exc.value)


def test_http_driver_network_error_handling() -> None:
    err = urllib.error.URLError(reason="Name or service not known")

    with patch("urllib.request.urlopen", side_effect=err):
        driver = HttpDriver("https://nonexistent-domain.xyz")
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "Network Error" in str(exc.value)


def test_http_driver_timeout_error_handling() -> None:
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Timed out")):
        driver = HttpDriver("https://timeout-domain.xyz", timeout=2.0)
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "Timeout Error" in str(exc.value)


def test_http_driver_empty_response_handling() -> None:
    with patch("urllib.request.urlopen", return_value=_make_mock_response("")):
        driver = HttpDriver("https://api.example.com/empty")
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "Empty Response" in str(exc.value)


def test_http_driver_invalid_payload_syntax_handling() -> None:
    with patch("urllib.request.urlopen", return_value=_make_mock_response("key: : [unclosed syntax")):
        driver = HttpDriver("https://api.example.com/bad_syntax")
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "Parsing Error" in str(exc.value)


def test_http_driver_schema_validation_error_handling() -> None:
    with patch("urllib.request.urlopen", return_value=_make_mock_response('{"unexpected_root": 123}')):
        driver = HttpDriver("https://api.example.com/bad_schema")
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "Schema Validation Error" in str(exc.value)


def test_http_driver_valid_json_but_not_dict_handling() -> None:
    with patch("urllib.request.urlopen", return_value=_make_mock_response("[1, 2, 3]")):
        driver = HttpDriver("https://api.example.com/list")
        with pytest.raises(TeraError) as exc:
            driver.load()
        assert "Invalid Payload" in str(exc.value)
