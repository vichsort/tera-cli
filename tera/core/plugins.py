import importlib
import importlib.metadata
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, cast

if TYPE_CHECKING:
    from tera.core.registry import DriverRegistry, WriterRegistry

_loaded_plugins: Set[str] = set()


def reset_plugins() -> None:
    """Resets the tracker of loaded plugins. Primarily used for testing."""
    _loaded_plugins.clear()


def _invoke_plugin_target(
    target: Any,
    driver_registry: "DriverRegistry",
    writer_registry: "WriterRegistry",
) -> None:
    """
    Invokes a plugin target object, module, or callable.
    Supports:
    - target(driver_registry, writer_registry)
    - target.register_tera_plugin(driver_registry, writer_registry)
    - target.register_plugin(driver_registry, writer_registry)
    - target.register(driver_registry, writer_registry)
    """
    if hasattr(target, "register_tera_plugin") and callable(getattr(target, "register_tera_plugin")):
        getattr(target, "register_tera_plugin")(driver_registry, writer_registry)
    elif hasattr(target, "register_plugin") and callable(getattr(target, "register_plugin")):
        getattr(target, "register_plugin")(driver_registry, writer_registry)
    elif hasattr(target, "register") and callable(getattr(target, "register")):
        getattr(target, "register")(driver_registry, writer_registry)
    elif callable(target):
        target(driver_registry, writer_registry)
    else:
        raise ValueError(f"Plugin target '{target}' does not provide a callable registration hook.")


def load_entry_point_plugins(
    driver_registry: "DriverRegistry",
    writer_registry: "WriterRegistry",
) -> List[str]:
    """
    Discovers and loads plugins exposed via Python entry points in the 'tera.plugins' group.
    Returns list of successfully loaded plugin names.
    """
    loaded: List[str] = []

    try:
        eps = importlib.metadata.entry_points(group="tera.plugins")
    except Exception:
        return loaded

    for ep in eps:
        ep_name = ep.name
        if ep_name in _loaded_plugins:
            continue

        try:
            target: Any = ep.load()
            _invoke_plugin_target(target, driver_registry, writer_registry)
            _loaded_plugins.add(ep_name)
            loaded.append(ep_name)
        except Exception:
            # Graceful error isolation: faulty third-party plugins must not crash core CLI
            continue

    return loaded


def load_toml_plugins(
    driver_registry: "DriverRegistry",
    writer_registry: "WriterRegistry",
    config_path: Optional[Path] = None,
) -> List[str]:
    """
    Discovers and loads plugins declared in 'tera.toml' under the [plugins] table.
    Returns list of successfully loaded plugin specifiers.
    """
    loaded: List[str] = []
    path = config_path if config_path is not None else Path.cwd() / "tera.toml"

    if not path.exists() or not path.is_file():
        return loaded

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return loaded

    plugins_cfg = data.get("plugins")
    if not isinstance(plugins_cfg, dict):
        return loaded
    plugins_dict = cast(Dict[str, Any], plugins_cfg)

    load_targets = plugins_dict.get("load")
    if not isinstance(load_targets, list):
        return loaded
    targets_list = cast(List[Any], load_targets)

    config_dir = str(path.parent.resolve())
    cwd_dir = str(Path.cwd().resolve())
    if config_dir not in sys.path:
        sys.path.insert(0, config_dir)
    if cwd_dir not in sys.path:
        sys.path.insert(0, cwd_dir)

    for item in targets_list:
        if not isinstance(item, str):
            continue

        specifier = item.strip()
        if not specifier or specifier in _loaded_plugins:
            continue

        try:
            if ":" in specifier:
                mod_name, attr_name = specifier.split(":", 1)
                mod = importlib.import_module(mod_name.strip())
                target = getattr(mod, attr_name.strip())
            else:
                target = importlib.import_module(specifier)

            _invoke_plugin_target(target, driver_registry, writer_registry)
            _loaded_plugins.add(specifier)
            loaded.append(specifier)
        except Exception:
            # Graceful error isolation
            continue

    return loaded


def load_plugins(
    driver_registry: "DriverRegistry",
    writer_registry: "WriterRegistry",
    config_path: Optional[Path] = None,
) -> Dict[str, List[str]]:
    """
    Convenience method to load both entry points and local tera.toml plugins.
    Returns dictionary with 'entry_points' and 'toml' lists of loaded plugins.
    """
    ep_loaded = load_entry_point_plugins(driver_registry, writer_registry)
    toml_loaded = load_toml_plugins(driver_registry, writer_registry, config_path=config_path)

    return {
        "entry_points": ep_loaded,
        "toml": toml_loaded,
    }
