import textwrap
from pathlib import Path
from tera.services.validation import ValidationService


def test_validation_service_valid_file(tmp_path: Path) -> None:
    doc_file = tmp_path / "docs.yaml"
    doc_file.write_text(
        textwrap.dedent("""
        api:
          name: Test API
          version: "1.0.0"
          description: A valid spec
        endpoints:
          - path: /ping
            method: GET
            summary: Ping endpoint
            responses:
              success:
                status: 200
                description: OK
        """),
        encoding="utf-8",
    )

    service = ValidationService()
    report = service.validate(doc_file)

    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.file_path == str(doc_file)


def test_validation_service_file_not_found(tmp_path: Path) -> None:
    ghost_file = tmp_path / "ghost.yaml"
    service = ValidationService()
    report = service.validate(ghost_file)

    assert report.is_valid is False
    assert len(report.errors) == 1
    assert report.errors[0].error_type == "file_not_found"


def test_validation_service_corrupted_file(tmp_path: Path) -> None:
    bad_file = tmp_path / "corrupted.yaml"
    bad_file.write_text("api: [unterminated", encoding="utf-8")

    service = ValidationService()
    report = service.validate(bad_file)

    assert report.is_valid is False
    assert len(report.errors) > 0


def test_validation_service_schema_error(tmp_path: Path) -> None:
    bad_schema = tmp_path / "bad_schema.yaml"
    bad_schema.write_text(
        textwrap.dedent("""
        api:
          # missing name and version
          title: Wrong Key
        endpoints:
          - path: /data
            method: INVALID_METHOD
        """),
        encoding="utf-8",
    )

    service = ValidationService()
    report = service.validate(bad_schema)

    assert report.is_valid is False
    assert len(report.errors) > 0
    locs = [err.location for err in report.errors]
    assert any("name" in loc for loc in locs) or any("api" in loc for loc in locs)

