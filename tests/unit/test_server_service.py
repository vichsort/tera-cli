from pathlib import Path
import json
import threading
import time
import urllib.request
import yaml

from tera.services.server import DocServer, SpecState


def create_sample_docs_yaml(path: Path, title: str = "Test API") -> None:
    content = f"""
api:
  name: "{title}"
  version: "1.0.0"
  description: "Server test description"
  base_url: "/api"

endpoints:
  - path: "/users"
    method: "GET"
    summary: "List users"
    responses:
      success:
        status: 200
        description: "Success"
"""
    path.write_text(content.strip(), encoding="utf-8")


def test_spec_state_dynamic_reload(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs.yaml"
    create_sample_docs_yaml(doc_path, title="Initial API")

    state = SpecState(doc_path)
    spec1, schema1 = state.get_openapi_dict()
    assert schema1.api.name == "Initial API"
    assert spec1["info"]["title"] == "Initial API"

    # Modify file and update mtime
    time.sleep(0.01)
    create_sample_docs_yaml(doc_path, title="Updated API")

    spec2, schema2 = state.get_openapi_dict()
    assert schema2.api.name == "Updated API"
    assert spec2["info"]["title"] == "Updated API"


def test_doc_server_http_endpoints(tmp_path: Path) -> None:
    doc_path = tmp_path / "docs.yaml"
    create_sample_docs_yaml(doc_path, title="HTTP Server API")

    state = SpecState(doc_path, default_ui="swagger")
    # Bind to port 0 to let OS assign an available free port
    server = DocServer(("127.0.0.1", 0), state)
    assigned_port = server.server_address[1]

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{assigned_port}"

    try:
        # Test GET / (Swagger UI default)
        with urllib.request.urlopen(f"{base_url}/") as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
            assert "<!DOCTYPE html>" in body
            assert "Swagger UI" in body
            assert "HTTP Server API" in body

        # Test GET /swagger
        with urllib.request.urlopen(f"{base_url}/swagger") as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
            assert "Swagger UI" in body

        # Test GET /redoc
        with urllib.request.urlopen(f"{base_url}/redoc") as resp:
            assert resp.status == 200
            body = resp.read().decode("utf-8")
            assert "Redoc" in body

        # Test GET /openapi.json
        with urllib.request.urlopen(f"{base_url}/openapi.json") as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "application/json; charset=utf-8"
            data = json.loads(resp.read().decode("utf-8"))
            assert data["openapi"] == "3.0.3"
            assert data["info"]["title"] == "HTTP Server API"
            assert "/users" in data["paths"]

        # Test GET /openapi.yaml
        with urllib.request.urlopen(f"{base_url}/openapi.yaml") as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "application/yaml; charset=utf-8"
            raw_yaml = yaml.safe_load(resp.read().decode("utf-8"))
            assert raw_yaml["openapi"] == "3.0.3"
            assert raw_yaml["info"]["title"] == "HTTP Server API"

    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)
