from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple, cast
import json
import logging
import urllib.parse
import webbrowser
import yaml

from tera.adapters.openapi import TeraOpenApiAdapter
from tera.domain.models import TeraSchema
from tera.drivers.yaml_driver import YamlFileDriver

logger = logging.getLogger(__name__)

SWAGGER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} - Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" />
  <style>
    body {{ margin: 0; padding: 0; background: #fafafa; }}
    .topbar {{ display: none; }}
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {{
      window.ui = SwaggerUIBundle({{
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout"
      }});
    }};
  </script>
</body>
</html>
"""

REDOC_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <title>{title} - Redoc</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
  <style>body {{ margin: 0; padding: 0; }}</style>
</head>
<body>
  <redoc spec-url="/openapi.json"></redoc>
  <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


class SpecState:
    """
    Thread-safe container that dynamically reloads the Tera schema from disk
    whenever the file's modification time changes.
    """

    def __init__(self, file_path: Path, default_ui: Literal["swagger", "redoc"] = "swagger") -> None:
        self.file_path = file_path
        self.default_ui: Literal["swagger", "redoc"] = default_ui
        self._last_mtime: float = 0.0
        self._cached_schema: Optional[TeraSchema] = None
        self._cached_openapi_dict: Optional[Dict[str, Any]] = None

    def get_openapi_dict(self) -> Tuple[Dict[str, Any], TeraSchema]:
        current_mtime = self.file_path.stat().st_mtime if self.file_path.exists() else 0.0
        if self._cached_schema is None or self._cached_openapi_dict is None or current_mtime > self._last_mtime:
            driver = YamlFileDriver(self.file_path)
            schema = driver.load()
            adapter = TeraOpenApiAdapter(schema)
            openapi_dict = adapter.convert()
            self._cached_schema = schema
            self._cached_openapi_dict = openapi_dict
            self._last_mtime = current_mtime

        return self._cached_openapi_dict, self._cached_schema


class TeraDocRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler serving Swagger UI, Redoc, and OpenAPI JSON/YAML.
    """

    @property
    def doc_server(self) -> "DocServer":
        return cast(DocServer, self.server)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard HTTP access logs in terminal
        pass

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        try:
            openapi_dict, schema = self.doc_server.spec_state.get_openapi_dict()
        except Exception as e:
            self._send_error_response(500, f"Error loading schema: {e}")
            return

        api_title = schema.api.name or "API Documentation"

        if path in ("/", "/docs"):
            if self.doc_server.spec_state.default_ui == "redoc":
                self._send_html_response(REDOC_HTML_TEMPLATE.format(title=api_title))
            else:
                self._send_html_response(SWAGGER_HTML_TEMPLATE.format(title=api_title))
        elif path == "/swagger":
            self._send_html_response(SWAGGER_HTML_TEMPLATE.format(title=api_title))
        elif path == "/redoc":
            self._send_html_response(REDOC_HTML_TEMPLATE.format(title=api_title))
        elif path == "/openapi.json":
            json_bytes = json.dumps(openapi_dict, indent=2, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(json_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json_bytes)
        elif path in ("/openapi.yaml", "/openapi.yml"):
            yaml_str = yaml.dump(openapi_dict, sort_keys=False, allow_unicode=True, indent=2)
            yaml_bytes = yaml_str.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/yaml; charset=utf-8")
            self.send_header("Content-Length", str(len(yaml_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(yaml_bytes)
        else:
            self._send_error_response(404, "Not Found")

    def _send_html_response(self, html_content: str) -> None:
        html_bytes = html_content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def _send_error_response(self, status_code: int, message: str) -> None:
        err_bytes = f"<h3>{status_code} - {message}</h3>".encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(err_bytes)))
        self.end_headers()
        self.wfile.write(err_bytes)


class DocServer(ThreadingHTTPServer):
    """
    Multi-threaded HTTP server dedicated to Tera documentation.
    """

    def __init__(
        self,
        server_address: Tuple[str, int],
        spec_state: SpecState,
    ) -> None:
        super().__init__(server_address, TeraDocRequestHandler)
        self.spec_state = spec_state


def run_server(
    file_path: Path,
    host: str = "127.0.0.1",
    port: int = 8000,
    ui: Literal["swagger", "redoc"] = "swagger",
    open_browser: bool = False,
) -> None:
    """
    Starts the documentation server on host:port, optionally opening the default browser.
    Blocks until interrupted via KeyboardInterrupt / SIGINT.
    """
    spec_state = SpecState(file_path=file_path, default_ui=ui)
    # Pre-flight check to fail fast if file doesn't exist or is invalid
    spec_state.get_openapi_dict()

    server = DocServer((host, port), spec_state)
    base_url = f"http://{host}:{port}"

    if open_browser:
        try:
            webbrowser.open(base_url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
