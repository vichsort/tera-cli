import textwrap
from pathlib import Path
from tera.core import TeraConfig
from tera.domain.linting import LintSeverity
from tera.services.linter import LinterService


def test_linter_service_valid_file(tmp_path: Path) -> None:
    doc_file = tmp_path / "valid.yaml"
    doc_file.write_text(
        textwrap.dedent("""
        api:
          name: Test API
          version: "1.0"
          description: A full description
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

    service = LinterService()
    issues = service.lint(doc_file)

    # Should have no issues
    assert len(issues) == 0


def test_linter_service_file_not_found(tmp_path: Path) -> None:
    non_existent = tmp_path / "ghost.yaml"
    service = LinterService()
    issues = service.lint(non_existent)

    assert len(issues) > 0
    assert any(i.severity == LintSeverity.ERROR for i in issues)


def test_linter_service_corrupted_yaml(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("api: [unterminated list", encoding="utf-8")

    service = LinterService()
    issues = service.lint(bad_yaml)

    assert len(issues) > 0
    assert any(i.severity == LintSeverity.ERROR for i in issues)


def test_linter_service_schema_validation_error(tmp_path: Path) -> None:
    invalid_schema = tmp_path / "invalid.yaml"
    invalid_schema.write_text(
        textwrap.dedent("""
        api:
          # missing required 'name' and 'version'
          title: Wrong Key
        endpoints:
          - path: /test
            method: INVALID_METHOD
        """),
        encoding="utf-8",
    )

    service = LinterService()
    issues = service.lint(invalid_schema)

    assert len(issues) > 0
    assert any(i.severity == LintSeverity.ERROR for i in issues)
    assert any(i.code == "schema_error" for i in issues)


def test_linter_service_semantic_warnings(tmp_path: Path) -> None:
    doc_file = tmp_path / "warnings.yaml"
    doc_file.write_text(
        textwrap.dedent("""
        api:
          name: Warning API
          version: "1.0"
          # missing description -> triggers missing_api_description
        endpoints:
          - path: /data
            method: DELETE
            summary: ""
            # empty summary + missing description -> triggers missing_description
            # write method without auth -> triggers unsafe_operation
            responses:
              success:
                status: 200
        """),
        encoding="utf-8",
    )

    service = LinterService()
    issues = service.lint(doc_file)

    assert len(issues) > 0
    codes = [i.code for i in issues]
    assert "missing_api_description" in codes
    assert "missing_description" in codes
    assert "unsafe_operation" in codes
    assert all(i.severity == LintSeverity.WARNING for i in issues)


def test_linter_service_filter_ignored(tmp_path: Path) -> None:
    doc_file = tmp_path / "ignored.yaml"
    doc_file.write_text(
        textwrap.dedent("""
        api:
          name: Ignore API
          version: "1.0"
        endpoints:
          - path: /ping
            method: GET
            summary: Ping
            responses:
              success:
                status: 200
        """),
        encoding="utf-8",
    )

    config = TeraConfig.model_validate(
        {"lint": {"ignore": ["missing_api_description"]}}
    )
    service = LinterService(config=config)
    issues = service.lint(doc_file)

    codes = [i.code for i in issues]
    assert "missing_api_description" not in codes
