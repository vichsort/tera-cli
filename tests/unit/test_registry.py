from pathlib import Path
import pytest
from tera.domain import TeraSchema, ApiConfig
from tera.core.registry import (
    DriverRegistry,
    WriterRegistry,
    default_driver_registry,
    default_writer_registry,
    parse_git_reference,
)


class DummyDriver:
    def __init__(self, source: str) -> None:
        self.source = source

    def load(self) -> TeraSchema:
        return TeraSchema(api=ApiConfig(name="Dummy", version="1.0.0"), endpoints=[])


class DummyWriter:
    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, schema: TeraSchema) -> None:
        pass


def test_default_driver_registry_contains_builtins() -> None:
    drivers = default_driver_registry.list_drivers()
    assert "flask" in drivers
    assert "git" in drivers
    assert "openapi" in drivers
    assert "tera" in drivers


def test_default_writer_registry_contains_builtins() -> None:
    writers = default_writer_registry.list_writers()
    assert "tera" in writers
    assert "openapi" in writers
    assert "markdown" in writers
    assert "html" in writers
    assert "postman" in writers


def test_driver_registry_custom_registration_and_explicit_get() -> None:
    registry = DriverRegistry()
    registry.register("dummy", lambda src: DummyDriver(src))

    assert "dummy" in registry.list_drivers()
    driver = registry.get("my_dummy_source", driver_type="dummy")
    assert isinstance(driver, DummyDriver)
    assert driver.source == "my_dummy_source"


def test_driver_registry_matcher_priority() -> None:
    registry = DriverRegistry()

    class DriverLow(DummyDriver):
        pass

    class DriverHigh(DummyDriver):
        pass

    # Register low priority first
    registry.register(
        "low",
        lambda src: DriverLow(src),
        matcher=lambda src: src.startswith("prefix_"),
        priority=10,
    )
    # Register high priority with same prefix condition but higher score
    registry.register(
        "high",
        lambda src: DriverHigh(src),
        matcher=lambda src: src.startswith("prefix_"),
        priority=90,
    )

    driver = registry.get("prefix_test")
    assert isinstance(driver, DriverHigh)


def test_driver_registry_unknown_type_raises_value_error() -> None:
    registry = DriverRegistry()
    registry.register("valid", lambda src: DummyDriver(src))

    with pytest.raises(ValueError) as exc:
        registry.get("some_source", driver_type="unknown")
    assert "Unknown driver type: 'unknown'" in str(exc.value)
    assert "valid" in str(exc.value)


def test_driver_registry_undetectable_source_raises_value_error() -> None:
    registry = DriverRegistry()

    with pytest.raises(ValueError) as exc:
        registry.get("unmatched_source")
    assert "Could not determine driver for input" in str(exc.value)


def test_writer_registry_custom_registration_and_get(tmp_path: Path) -> None:
    registry = WriterRegistry()
    registry.register("custom", lambda p: DummyWriter(p))

    assert "custom" in registry.list_writers()
    out = tmp_path / "out.txt"
    writer = registry.get(out, format_style="custom")
    assert isinstance(writer, DummyWriter)
    assert writer.path == out


def test_writer_registry_unknown_format_raises_value_error(tmp_path: Path) -> None:
    registry = WriterRegistry()
    registry.register("tera", lambda p: DummyWriter(p))

    out = tmp_path / "out.txt"
    with pytest.raises(ValueError) as exc:
        registry.get(out, format_style="pdf")
    assert "Unknown format style: 'pdf'" in str(exc.value)


def test_parse_git_reference() -> None:
    rev1, path1 = parse_git_reference("git:HEAD~1:api.yaml")
    assert rev1 == "HEAD~1"
    assert path1 == "api.yaml"

    rev2, path2 = parse_git_reference("HEAD:spec.json")
    assert rev2 == "HEAD"
    assert path2 == "spec.json"

    rev3, path3 = parse_git_reference("main")
    assert rev3 == "main"
    assert path3 == "docs.yaml"
