import pytest
from pathlib import Path
from tera.domain import (
    TeraSchema,
    ApiConfig,
    Endpoint,
    EndpointParams,
    ParamField,
    EndpointResponses,
    ResponseSuccess
)
from tera.services import DiffService, SemverService
from tera.exceptions import TeraError

@pytest.fixture
def sample_spec() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="Demo API", version="1.2.3"),
        endpoints=[
            Endpoint(
                path="/items",
                method="GET",
                summary="List items",
                params=EndpointParams(
                    query=[ParamField(name="limit", type="integer", required=False)]
                ),
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Items")
                )
            )
        ]
    )

def test_semver_parse_version() -> None:
    service = SemverService()
    assert service.parse_version("1.2.3") == (1, 2, 3)
    assert service.parse_version("v2.0.1") == (2, 0, 1)
    assert service.parse_version("0.1.0-alpha.1") == (0, 1, 0)

    with pytest.raises(TeraError):
        service.parse_version("invalid-version")

    with pytest.raises(TeraError):
        service.parse_version("1.2")

def test_semver_no_bump(sample_spec: TeraSchema) -> None:
    diff_service = DiffService()
    semver_service = SemverService()

    diff = diff_service.compare(sample_spec, sample_spec)
    result = semver_service.calculate_bump(diff, sample_spec.api.version)

    assert result.bump == "none"
    assert result.next_version == "1.2.3"
    assert result.breaking_count == 0

def test_semver_major_bump(sample_spec: TeraSchema) -> None:
    head = sample_spec.model_copy(deep=True)
    # Remove the endpoint -> breaking change
    head.endpoints = []

    diff_service = DiffService()
    semver_service = SemverService()

    diff = diff_service.compare(sample_spec, head)
    result = semver_service.calculate_bump(diff, sample_spec.api.version)

    assert result.bump == "major"
    assert result.next_version == "2.0.0"
    assert result.breaking_count == 1
    assert len(result.reasons) > 0

def test_semver_minor_bump(sample_spec: TeraSchema) -> None:
    head = sample_spec.model_copy(deep=True)
    # Add new endpoint -> backwards compatible feature
    head.endpoints.append(
        Endpoint(
            path="/items",
            method="POST",
            summary="Create item",
            responses=EndpointResponses(
                success=ResponseSuccess(status=201, description="Created")
            )
        )
    )

    diff_service = DiffService()
    semver_service = SemverService()

    diff = diff_service.compare(sample_spec, head)
    result = semver_service.calculate_bump(diff, sample_spec.api.version)

    assert result.bump == "minor"
    assert result.next_version == "1.3.0"
    assert result.breaking_count == 0

def test_semver_patch_bump(sample_spec: TeraSchema) -> None:
    head = sample_spec.model_copy(deep=True)
    # Only summary changed -> patch bump
    head.endpoints[0].summary = "List items (updated summary)"

    diff_service = DiffService()
    semver_service = SemverService()

    diff = diff_service.compare(sample_spec, head)
    result = semver_service.calculate_bump(diff, sample_spec.api.version)

    assert result.bump == "patch"
    assert result.next_version == "1.2.4"
    assert result.breaking_count == 0

def test_apply_bump_yaml(tmp_path: Path) -> None:
    yaml_file = tmp_path / "docs.yaml"
    yaml_file.write_text("""# Header comment
api:
  name: Demo API
  version: "1.0.0"
  base_url: /v1

endpoints: []
""", encoding="utf-8")

    service = SemverService()
    service.apply_bump(yaml_file, "1.1.0")

    content = yaml_file.read_text(encoding="utf-8")
    assert 'version: "1.1.0"' in content
    assert "# Header comment" in content

def test_apply_bump_json(tmp_path: Path) -> None:
    json_file = tmp_path / "docs.json"
    json_file.write_text('{"api": {"name": "Demo", "version": "1.0.0"}, "endpoints": []}', encoding="utf-8")

    service = SemverService()
    service.apply_bump(json_file, "2.0.0")

    content = json_file.read_text(encoding="utf-8")
    assert '"version": "2.0.0"' in content
