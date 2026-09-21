import sys
from pathlib import Path
from typing import List, Dict, Any, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from tera.core import TeraConfig

CONFIG_FILENAME = ".teraconfig.toml"
IGNORE_FILENAME = ".teraignore"

def load_config(root_path: Path = Path(".")) -> TeraConfig:
    """
    Loads the configuration from the filesystem.
    """
    
    config_data: Dict[str, Any] = {}
    toml_path = root_path / CONFIG_FILENAME
    
    if toml_path.exists():
        try:
            with open(toml_path, "rb") as f:
                raw: Any = tomllib.load(f)
                if isinstance(raw, dict):
                    config_data = cast(Dict[str, Any], raw)
        except Exception as e:
            print(f"⚠️  Warning: Failed to parse {CONFIG_FILENAME}: {e}")

    config = TeraConfig.model_validate(config_data)

    ignore_path = root_path / IGNORE_FILENAME
    if ignore_path.exists():
        extra_patterns = _read_ignore_file(ignore_path)
        config.ignore.extend(extra_patterns)
        config.ignore = list(dict.fromkeys(config.ignore))

    return config

def _read_ignore_file(path: Path) -> List[str]:
    """
    Reads .teraignore treating comments as empty lines.
    """
    patterns: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except Exception:
        pass
        
    return patterns