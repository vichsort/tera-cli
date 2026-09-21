import pytest
from pathlib import Path
from tera.services.init import InitService


def test_init_service_standard_mode(tmp_path: Path) -> None:
    service = InitService()
    dest_yaml, dest_config = service.create_project(tmp_path, complete_mode=False, skip_config=False)

    assert dest_yaml.exists()
    assert dest_yaml.name == "docs.yaml"
    assert dest_config is not None
    assert dest_config.exists()
    assert dest_config.name == ".teraconfig.toml"

    yaml_content = dest_yaml.read_text(encoding="utf-8")
    assert "api:" in yaml_content
    assert "endpoints:" in yaml_content


def test_init_service_complete_mode(tmp_path: Path) -> None:
    service = InitService()
    dest_yaml, dest_config = service.create_project(tmp_path, complete_mode=True, skip_config=False)

    assert dest_yaml.exists()
    assert dest_config is not None
    assert dest_config.exists()

    yaml_content = dest_yaml.read_text(encoding="utf-8")
    assert "api:" in yaml_content
    assert "auth:" in yaml_content or "endpoints:" in yaml_content


def test_init_service_skip_config(tmp_path: Path) -> None:
    service = InitService()
    dest_yaml, dest_config = service.create_project(tmp_path, complete_mode=False, skip_config=True)

    assert dest_yaml.exists()
    assert dest_config is None
    assert not (tmp_path / ".teraconfig.toml").exists()


def test_init_service_template_missing(tmp_path: Path) -> None:
    service = InitService()
    service.templates_dir = tmp_path / "non_existent_dir"

    with pytest.raises(FileNotFoundError, match="Template not found"):
        service.create_project(tmp_path)
