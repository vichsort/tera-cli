from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from tera.contracts import TeraDriver, TeraWriter
from tera.drivers import (
    YamlFileDriver,
    FlaskAppDriver,
    OpenApiDriver,
    GitFileDriver,
    FastApiDriver,
    HttpDriver,
    PostmanCollectionDriver,
    HarDriver,
)
from tera.writers import (
    JsonFileWriter,
    YamlFileWriter,
    OpenApiJsonWriter,
    OpenApiYamlWriter,
    MarkdownWriter,
    HtmlWriter,
    PostmanWriter,
)

DriverFactory = Callable[[Any], TeraDriver]
DriverMatcher = Callable[[Any], bool]
WriterFactory = Callable[[Path], TeraWriter]


def parse_git_reference(source_str: str) -> Tuple[str, str]:
    """Extracts git revision and file path from a git reference string."""
    git_target = source_str[4:] if source_str.startswith("git:") else source_str
    if ":" in git_target:
        parts = git_target.split(":", 1)
        return parts[0], parts[1] if parts[1] else "docs.yaml"
    return git_target, "docs.yaml"


# Matcher functions for built-in drivers
def _is_explicit_git_ref(source: Any) -> bool:
    return isinstance(source, str) and source.startswith("git:")


def _is_http_url(source: Any) -> bool:
    return isinstance(source, str) and (source.startswith("http://") or source.startswith("https://"))



def _is_local_openapi_file(source: Any) -> bool:
    if not isinstance(source, (str, Path)):
        return False
    p = Path(source)
    if p.exists() and p.is_file() and p.suffix.lower() in (".json", ".yaml", ".yml"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                header = f.read(512)
                return any(
                    kw in header
                    for kw in (
                        '"openapi"',
                        "'openapi'",
                        "openapi:",
                        '"swagger"',
                        "'swagger'",
                        "swagger:",
                    )
                )
        except Exception:
            return False
    return False


def _is_postman_collection(source: Any) -> bool:
    if isinstance(source, dict):
        source_dict = cast(Dict[str, Any], source)
        info = source_dict.get("info")
        if isinstance(info, dict):
            info_dict = cast(Dict[str, Any], info)
            schema_url = str(info_dict.get("schema", ""))
            if "postman.com" in schema_url:
                return True
        if "requests" in source_dict and isinstance(source_dict.get("requests"), list):
            return True
        return False

    if not isinstance(source, (str, Path)):
        return False

    p = Path(source)
    if p.exists() and p.is_file() and p.suffix.lower() == ".json":
        try:
            with open(p, "r", encoding="utf-8") as f:
                header = f.read(512)
                if "postman.com/json/collection" in header or "schema.getpostman.com" in header:
                    return True
                if '"requests"' in header and ('"folders"' in header or '"order"' in header):
                    return True
        except Exception:
            return False
    return False


def _is_har_file(source: Any) -> bool:
    if isinstance(source, dict):
        source_dict = cast(Dict[str, Any], source)
        log_val = source_dict.get("log")
        if isinstance(log_val, dict):
            log_dict = cast(Dict[str, Any], log_val)
            return "entries" in log_dict
        return False

    if not isinstance(source, (str, Path)):
        return False

    p = Path(source)
    if not (p.exists() and p.is_file()):
        return False

    if p.suffix.lower() == ".har":
        return True

    if p.suffix.lower() == ".json":
        try:
            with open(p, "r", encoding="utf-8") as f:
                header = f.read(512)
                if '"log"' in header and ('"entries"' in header or '"version"' in header):
                    return True
        except Exception:
            return False
    return False


def _is_local_tera_file(source: Any) -> bool:
    if not isinstance(source, (str, Path)):
        return False
    p = Path(source)
    return p.exists() and p.is_file() and p.suffix.lower() in (".json", ".yaml", ".yml")


def _is_git_colon_ref(source: Any) -> bool:
    if not isinstance(source, str):
        return False
    p = Path(source)
    if p.exists() and p.is_file():
        return False
    if ":" in source:
        left, right = source.split(":", 1)
        return bool(
            right.endswith((".yaml", ".yml", ".json"))
            or left.startswith("HEAD")
            or "~" in left
            or "^" in left
            or "/" in right
        )
    return False


def _is_flask_import_str(source: Any) -> bool:
    if not isinstance(source, str):
        return False
    p = Path(source)
    if p.exists() and p.is_file():
        return False
    if ":" in source:
        left, right = source.split(":", 1)
        return not (
            right.endswith((".yaml", ".yml", ".json"))
            or left.startswith("HEAD")
            or "~" in left
            or "^" in left
            or "/" in right
        )
    return False


def _is_fastapi_target(source: Any) -> bool:
    if hasattr(source, "openapi") and callable(getattr(source, "openapi")):
        return True
    if not isinstance(source, str) or not _is_flask_import_str(source):
        return False
    try:
        from tera.drivers.inspection.loader import load_app_instance
        instance = load_app_instance(source)
        if hasattr(instance, "openapi") and callable(getattr(instance, "openapi")):
            return True
        if callable(instance) and not hasattr(instance, "url_map"):
            app = instance()
            return hasattr(app, "openapi") and callable(getattr(app, "openapi"))
    except Exception:
        return False
    return False


def _is_spec_file_path(source: Any) -> bool:
    return isinstance(source, (str, Path)) and str(source).endswith((".yaml", ".yml", ".json"))


class DriverRegistry:
    """
    Registry for input drivers (TeraDriver).
    Supports named registration, custom factories, and prioritized matchers for auto-detection.
    """

    def __init__(self) -> None:
        self._drivers: Dict[str, DriverFactory] = {}
        self._matchers: List[Tuple[int, DriverMatcher, str]] = []

    def register(
        self,
        name: str,
        factory: DriverFactory,
        matcher: Optional[DriverMatcher] = None,
        priority: int = 50,
    ) -> None:
        """Registers a driver factory with an optional auto-detection matcher."""
        self._drivers[name] = factory
        if matcher is not None:
            self.add_matcher(name, matcher, priority)

    def add_matcher(
        self,
        driver_name: str,
        matcher: DriverMatcher,
        priority: int = 50,
    ) -> None:
        """Registers an auto-detection matcher associated with a driver name."""
        self._matchers.append((priority, matcher, driver_name))
        self._matchers.sort(key=lambda item: item[0], reverse=True)

    def get(
        self,
        source: Any,
        driver_type: Optional[str] = None,
    ) -> TeraDriver:
        """
        Resolves and instantiates a driver for the given source and optional driver_type.
        """
        if driver_type is not None:
            factory = self._drivers.get(driver_type)
            if not factory:
                supported = ", ".join(sorted(self._drivers.keys()))
                raise ValueError(
                    f"Unknown driver type: '{driver_type}'. Supported driver types: {supported}"
                )
            return factory(source)

        for _, matcher, driver_name in self._matchers:
            try:
                if matcher(source):
                    factory = self._drivers.get(driver_name)
                    if factory:
                        return factory(source)
            except Exception:
                continue

        supported_formats = (
            "Supported formats: .yaml/.json files, 'git:rev:path' references, or 'module:app' strings."
        )
        raise ValueError(
            f"Could not determine driver for input: '{source}'. {supported_formats}"
        )

    def list_drivers(self) -> List[str]:
        """Returns sorted list of registered driver names."""
        return sorted(self._drivers.keys())


class WriterRegistry:
    """
    Registry for output writers (TeraWriter).
    Maps format styles to factory callables.
    """

    def __init__(self) -> None:
        self._writers: Dict[str, WriterFactory] = {}

    def register(self, format_style: str, factory: WriterFactory) -> None:
        """Registers a writer factory for a format style."""
        self._writers[format_style] = factory

    def get(self, output_path: Path, format_style: str = "tera") -> TeraWriter:
        """Resolves and instantiates a writer for the given output path and format style."""
        factory = self._writers.get(format_style)
        if not factory:
            supported = ", ".join(sorted(self._writers.keys()))
            raise ValueError(
                f"Unknown format style: '{format_style}'. Supported formats: {supported}"
            )
        return factory(output_path)

    def list_writers(self) -> List[str]:
        """Returns sorted list of registered writer format styles."""
        return sorted(self._writers.keys())


# Built-in factories
def _git_driver_factory(source: Any) -> TeraDriver:
    rev, file_path = parse_git_reference(str(source))
    return GitFileDriver(rev, file_path)


def _openapi_driver_factory(source: Any) -> TeraDriver:
    if isinstance(source, dict):
        return OpenApiDriver(cast(Dict[str, Any], source))
    return OpenApiDriver(Path(str(source)))


def _flask_driver_factory(source: Any) -> TeraDriver:
    return FlaskAppDriver(str(source))


def _tera_driver_factory(source: Any) -> TeraDriver:
    return YamlFileDriver(Path(str(source)))


def _fastapi_driver_factory(source: Any) -> TeraDriver:
    return FastApiDriver(source)


def _http_driver_factory(source: Any) -> TeraDriver:
    return HttpDriver(str(source))


def _postman_driver_factory(source: Any) -> TeraDriver:
    if isinstance(source, dict):
        return PostmanCollectionDriver(cast(Dict[str, Any], source))
    return PostmanCollectionDriver(Path(str(source)))


def _har_driver_factory(source: Any) -> TeraDriver:
    if isinstance(source, dict):
        return HarDriver(cast(Dict[str, Any], source))
    return HarDriver(Path(str(source)))


def register_builtin_drivers(registry: DriverRegistry) -> None:
    registry.register("git", _git_driver_factory, matcher=_is_explicit_git_ref, priority=100)
    registry.add_matcher("git", _is_git_colon_ref, priority=70)

    registry.register("http", _http_driver_factory, matcher=_is_http_url, priority=95)

    registry.register("openapi", _openapi_driver_factory, matcher=_is_local_openapi_file, priority=90)

    registry.register("postman", _postman_driver_factory, matcher=_is_postman_collection, priority=85)

    registry.register("har", _har_driver_factory, matcher=_is_har_file, priority=85)

    registry.register("tera", _tera_driver_factory, matcher=_is_local_tera_file, priority=80)
    registry.add_matcher("tera", _is_spec_file_path, priority=50)

    registry.register("fastapi", _fastapi_driver_factory, matcher=_is_fastapi_target, priority=65)

    registry.register("flask", _flask_driver_factory, matcher=_is_flask_import_str, priority=60)


def _tera_writer_factory(output_path: Path) -> TeraWriter:
    if output_path.suffix in [".yaml", ".yml"]:
        return YamlFileWriter(output_path)
    return JsonFileWriter(output_path)


def _openapi_writer_factory(output_path: Path) -> TeraWriter:
    if output_path.suffix in [".yaml", ".yml"]:
        return OpenApiYamlWriter(output_path)
    return OpenApiJsonWriter(output_path)


def register_builtin_writers(registry: WriterRegistry) -> None:
    registry.register("tera", _tera_writer_factory)
    registry.register("openapi", _openapi_writer_factory)
    registry.register("markdown", lambda p: MarkdownWriter(p))
    registry.register("html", lambda p: HtmlWriter(p))
    registry.register("postman", lambda p: PostmanWriter(p))


def create_default_driver_registry() -> DriverRegistry:
    registry = DriverRegistry()
    register_builtin_drivers(registry)
    return registry


def create_default_writer_registry() -> WriterRegistry:
    registry = WriterRegistry()
    register_builtin_writers(registry)
    return registry


default_driver_registry: DriverRegistry = create_default_driver_registry()
default_writer_registry: WriterRegistry = create_default_writer_registry()

