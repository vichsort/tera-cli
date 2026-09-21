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
from tera.services import DiffService, ChangelogService

@pytest.fixture
def base_spec() -> TeraSchema:
    return TeraSchema(
        api=ApiConfig(name="API", version="1.0.0"),
        endpoints=[
            Endpoint(
                path="/items",
                method="GET",
                summary="List items",
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Items")
                )
            ),
            Endpoint(
                path="/items/{id}",
                method="DELETE",
                summary="Delete item",
                responses=EndpointResponses(
                    success=ResponseSuccess(status=200, description="Deleted")
                )
            )
        ]
    )

def test_generate_changelog_categorization(base_spec: TeraSchema) -> None:
    head = base_spec.model_copy(deep=True)
    # Remove DELETE /items/{id}
    head.endpoints = [ep for ep in head.endpoints if ep.method != "DELETE"]
    # Add POST /items
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
    # Modify GET /items: add query param + require auth
    get_ep = next(ep for ep in head.endpoints if ep.method == "GET")
    get_ep.params = EndpointParams(query=[ParamField(name="search", type="string")])
    get_ep.auth_required = True

    diff_service = DiffService()
    changelog_service = ChangelogService()

    diff = diff_service.compare(base_spec, head)
    section = changelog_service.generate(diff, version="1.1.0", release_date="2026-09-21")

    assert section.version == "1.1.0"
    assert section.release_date == "2026-09-21"
    assert any("Added endpoint `POST /items`" in entry for entry in section.added)
    assert any("Removed endpoint `DELETE /items/{id}`" in entry for entry in section.removed)
    assert any("requires authentication" in entry for entry in section.security)
    assert any("search" in entry for entry in section.added)

    md = section.to_markdown()
    assert "## [1.1.0] - 2026-09-21" in md
    assert "### Added" in md
    assert "### Removed" in md
    assert "### Security" in md

def test_generate_changelog_empty_diff(base_spec: TeraSchema) -> None:
    diff_service = DiffService()
    changelog_service = ChangelogService()

    diff = diff_service.compare(base_spec, base_spec)
    section = changelog_service.generate(diff, version="1.0.0")

    assert len(section.added) == 0
    assert len(section.changed) == 0
    assert len(section.removed) == 0
    md = section.to_markdown()
    assert "No API changes recorded" in md

def test_append_to_file_new_and_existing(tmp_path: Path, base_spec: TeraSchema) -> None:
    changelog_file = tmp_path / "CHANGELOG.md"
    diff_service = DiffService()
    changelog_service = ChangelogService()

    diff = diff_service.compare(base_spec, base_spec)
    section_v1 = changelog_service.generate(diff, version="1.0.0", release_date="2026-09-01")

    # First append creates file with header
    changelog_service.append_to_file(changelog_file, section_v1)
    content1 = changelog_file.read_text(encoding="utf-8")
    assert "# Changelog" in content1
    assert "## [1.0.0] - 2026-09-01" in content1

    # Second append prepends new version before 1.0.0
    section_v2 = changelog_service.generate(diff, version="1.1.0", release_date="2026-09-21")
    changelog_service.append_to_file(changelog_file, section_v2)
    content2 = changelog_file.read_text(encoding="utf-8")

    assert content2.index("## [1.1.0]") < content2.index("## [1.0.0]")
