"""
Sample tera-cli custom plugin.

Demonstrates how to implement and register custom drivers and writers
via tera.toml [plugins.load] or Python entry points.
"""

from pathlib import Path
from typing import Any, List
from tera.contracts import TeraDriver, TeraWriter
from tera.core.registry import DriverRegistry, WriterRegistry
from tera.domain import (
    ApiConfig,
    Endpoint,
    EndpointParams,
    EndpointResponses,
    FieldType,
    ParamField,
    ResponseSuccess,
    TeraSchema,
)
from tera.domain.models import HTTPMethod


class CustomRouteListDriver(TeraDriver):
    """
    Toy driver that parses a plain text route list file (.routes).
    Lines follow the format: 'METHOD /path # Description'
    """

    def __init__(self, source: Any) -> None:
        self.source = Path(str(source))

    def load(self) -> TeraSchema:
        if not self.source.exists():
            raise FileNotFoundError(f"Routes file '{self.source}' not found.")

        lines = self.source.read_text(encoding="utf-8").splitlines()
        endpoints: List[Endpoint] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse comments
            desc = "Auto-generated from routes plugin"
            if "#" in line:
                line, comment = line.split("#", 1)
                line = line.strip()
                desc = comment.strip()

            parts = line.split()
            if not parts:
                continue

            method_str = parts[0].upper()
            path_str = parts[1] if len(parts) > 1 else parts[0]
            if not path_str.startswith("/"):
                path_str = "/" + path_str

            valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
            method: HTTPMethod = method_str if method_str in valid_methods else "GET"  # type: ignore

            endpoints.append(
                Endpoint(
                    path=path_str,
                    method=method,
                    summary=f"{method} {path_str}",
                    description=desc,
                    params=EndpointParams(path=[], query=[], header=[]),
                    body=[],
                    responses=EndpointResponses(
                        success=ResponseSuccess(
                            status=200 if method != "POST" else 201,
                            example={"status": "ok", "path": path_str},
                        )
                    ),
                )
            )

        return TeraSchema(
            api=ApiConfig(
                name="Custom Routes Plugin API",
                version="1.0.0",
                description="Parsed by CustomRouteListDriver plugin",
            ),
            endpoints=endpoints,
        )


def register_tera_plugin(
    driver_registry: DriverRegistry,
    writer_registry: WriterRegistry,
) -> None:
    """
    Hook called by tera-cli upon loading this plugin.
    Registers CustomRouteListDriver with matcher for '.routes' files.
    """
    driver_registry.register(
        "routes",
        lambda source: CustomRouteListDriver(source),
        matcher=lambda s: isinstance(s, (str, Path)) and str(s).endswith(".routes"),
        priority=85,
    )

