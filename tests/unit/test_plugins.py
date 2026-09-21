from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from tera.contracts import TeraDriver, TeraWriter
from tera.core.plugins import (
    load_entry_point_plugins,
    load_plugins,
    load_toml_plugins,
    reset_plugins,
)
from tera.core.registry import DriverRegistry, WriterRegistry
from tera.domain.models import ApiConfig, TeraSchema


class DummyCustomDriver(TeraDriver):
    def __init__(self, source: Any) -> None:
        self.source = source

    def load(self) -> TeraSchema:
        return TeraSchema(api=ApiConfig(name="Custom Driver", version="1.0.0"), endpoints=[])


class DummyCustomWriter(TeraWriter):
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path

    def write(self, schema: TeraSchema) -> None:
        pass


def sample_callable_hook(driver_registry: DriverRegistry, writer_registry: WriterRegistry) -> None:
    driver_registry.register("dummy", lambda s: DummyCustomDriver(s))
    writer_registry.register("dummy", lambda p: DummyCustomWriter(p))


class SampleClassPlugin:
    @staticmethod
    def register_tera_plugin(driver_registry: DriverRegistry, writer_registry: WriterRegistry) -> None:
        driver_registry.register("dummy_class", lambda s: DummyCustomDriver(s))


def test_entry_point_plugin_callable() -> None:
    reset_plugins()
    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()

    mock_ep = MagicMock()
    mock_ep.name = "my_custom_plugin"
    mock_ep.load.return_value = sample_callable_hook

    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loaded = load_entry_point_plugins(driver_reg, writer_reg)

    assert "my_custom_plugin" in loaded
    assert "dummy" in driver_reg.list_drivers()
    assert "dummy" in writer_reg.list_writers()


def test_entry_point_plugin_class_hook() -> None:
    reset_plugins()
    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()

    mock_ep = MagicMock()
    mock_ep.name = "class_plugin"
    mock_ep.load.return_value = SampleClassPlugin

    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        loaded = load_entry_point_plugins(driver_reg, writer_reg)

    assert "class_plugin" in loaded
    assert "dummy_class" in driver_reg.list_drivers()


def test_entry_point_plugin_error_isolation(capsys: Any) -> None:
    reset_plugins()
    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()

    crashing_ep = MagicMock()
    crashing_ep.name = "faulty_plugin"
    crashing_ep.load.side_effect = RuntimeError("Broken external dependency")

    valid_ep = MagicMock()
    valid_ep.name = "valid_plugin"
    valid_ep.load.return_value = sample_callable_hook

    with patch("importlib.metadata.entry_points", return_value=[crashing_ep, valid_ep]):
        loaded = load_entry_point_plugins(driver_reg, writer_reg)

    assert "faulty_plugin" not in loaded
    assert "valid_plugin" in loaded
    assert "dummy" in driver_reg.list_drivers()
    captured = capsys.readouterr()
    assert "Failed to load entry point plugin 'faulty_plugin'" in captured.err


def test_load_toml_plugins_valid(tmp_path: Path) -> None:
    reset_plugins()
    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()

    plugin_file = tmp_path / "my_local_plugin.py"
    plugin_file.write_text(
        """
class DummyDriver:
    def __init__(self, source):
        self.source = source
    def load(self):
        return None

def register_tera_plugin(driver_registry, writer_registry):
    driver_registry.register("local_test", lambda s: DummyDriver(s))
""",
        encoding="utf-8",
    )

    toml_file = tmp_path / "tera.toml"
    toml_file.write_text(
        """
[plugins]
load = [
    "my_local_plugin:register_tera_plugin"
]
""",
        encoding="utf-8",
    )

    loaded = load_toml_plugins(driver_reg, writer_reg, config_path=toml_file)
    assert "my_local_plugin:register_tera_plugin" in loaded
    assert "local_test" in driver_reg.list_drivers()


def test_load_toml_plugins_resilience(tmp_path: Path, capsys: Any) -> None:
    reset_plugins()
    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()

    # Non-existent file
    assert load_toml_plugins(driver_reg, writer_reg, config_path=tmp_path / "absent.toml") == []

    # Malformed TOML
    broken_toml = tmp_path / "broken.toml"
    broken_toml.write_text("[plugins\nload = broken", encoding="utf-8")
    assert load_toml_plugins(driver_reg, writer_reg, config_path=broken_toml) == []
    captured = capsys.readouterr()
    assert "Failed to parse plugin configuration" in captured.err

    # Deprecated drivers/writers keys warning
    legacy_toml = tmp_path / "legacy.toml"
    legacy_toml.write_text("[plugins]\ndrivers = ['foo']\nwriters = ['bar']", encoding="utf-8")
    assert load_toml_plugins(driver_reg, writer_reg, config_path=legacy_toml) == []
    captured = capsys.readouterr()
    assert "are not supported" in captured.err

    # Non-existent module in load table
    invalid_mod_toml = tmp_path / "invalid_mod.toml"
    invalid_mod_toml.write_text(
        """
[plugins]
load = [
    "non_existent_package_foo_bar_xyz:hook"
]
""",
        encoding="utf-8",
    )
    loaded = load_toml_plugins(driver_reg, writer_reg, config_path=invalid_mod_toml)
    assert loaded == []
    captured = capsys.readouterr()
    assert "Failed to load plugin 'non_existent_package_foo_bar_xyz:hook'" in captured.err


def test_load_plugins_idempotency(tmp_path: Path) -> None:
    reset_plugins()
    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()

    plugin_file = tmp_path / "idempotent_plugin.py"
    plugin_file.write_text(
        """
def register_tera_plugin(driver_registry, writer_registry):
    pass
""",
        encoding="utf-8",
    )

    toml_file = tmp_path / "tera.toml"
    toml_file.write_text(
        """
[plugins]
load = ["idempotent_plugin:register_tera_plugin"]
""",
        encoding="utf-8",
    )

    first_result = load_plugins(driver_reg, writer_reg, config_path=toml_file)
    assert len(first_result["toml"]) == 1

    # Second run without reset should not re-run the same plugin
    second_result = load_plugins(driver_reg, writer_reg, config_path=toml_file)
    assert len(second_result["toml"]) == 0


def test_example_plugin_integration() -> None:
    reset_plugins()
    plugin_dir = Path(__file__).resolve().parent.parent.parent / "examples" / "plugin_example"
    toml_path = plugin_dir / "tera.toml"
    routes_path = plugin_dir / "api.routes"
    assert toml_path.exists()
    assert routes_path.exists()

    driver_reg = DriverRegistry()
    writer_reg = WriterRegistry()
    loaded = load_toml_plugins(driver_reg, writer_reg, config_path=toml_path)
    assert len(loaded) == 1
    assert "routes" in driver_reg.list_drivers()

    driver = driver_reg.get(routes_path)
    schema = driver.load()
    assert schema.api.name == "Custom Routes Plugin API"
    assert len(schema.endpoints) == 4
    paths = [ep.path for ep in schema.endpoints]
    assert "/api/v1/health" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/metrics" in paths
