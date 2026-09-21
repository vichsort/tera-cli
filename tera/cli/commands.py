from datetime import date
from pathlib import Path
from typing import Optional, Union, cast
from pydantic import ValidationError
import typer

from tera.contracts import TeraDriver
from tera.core import factory, loader
from tera.core.factory import WriterFormatStyle
from tera.domain import LintSeverity
from tera.drivers import YamlFileDriver
from tera.exceptions import TeraError
from tera.domain.models import TeraSchema
from tera.services import (
    AuditService,
    ChangelogService,
    CoverageService,
    DiffService,
    GraphService,
    InitService,
    LinterService,
    SecurityDriftService,
    SemverService,
    SyncService,
    ValidationService,
    export_ir_json_schema,
    load_schema_from_source,
    run_pipeline,
    run_server,
)
from tera.cli.presenters import (
    print_error,
    print_json,
    print_success,
    print_validation_error,
    present_audit_report,
    present_coverage_report,
    present_diff_report,
    present_lint_report,
    present_security_report,
    present_semver_report,
    present_sync_report,
    present_validation_report,
)

# Compatibility aliases
_print_error = print_error
_print_success = print_success
_print_validation_error = print_validation_error

app = typer.Typer(help="Tera CLI - Documentation Converter")


def _load_schema_or_exit(source: Union[str, Path], label: str = "Specification") -> TeraSchema:
    """Helper function to load a schema from source or exit cleanly with a standard error message."""
    try:
        return load_schema_from_source(source)
    except FileNotFoundError as e:
        print_error(f"{label} Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error(f"Error Loading {label}", str(e))
        raise typer.Exit(code=1)


def _execute_pipeline(
    input_source: Union[str, TeraDriver],
    output_path: Path,
    format_style: WriterFormatStyle = "tera",
    source_label: Optional[str] = None,
) -> None:
    """
    Helper function to execute the pipeline safely.
    Connects: Factory -> Pipeline -> UI
    """
    try:
        if isinstance(input_source, str):
            driver = factory.get_driver(input_source)
            display_source = source_label or input_source
        else:
            driver = input_source
            display_source = (
                source_label
                or getattr(driver, "import_string", None)
                or getattr(driver, "file_path", None)
                or getattr(driver, "source", None)
                or driver.__class__.__name__
            )

        writer = factory.get_writer(output_path, format_style=format_style)

        run_pipeline(driver, writer)
        print_success(str(display_source), str(output_path))

    except ValidationError as e:
        print_validation_error(e)
        raise typer.Exit(code=1)
    except TeraError as e:
        print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        print_error("File Not Found", str(e))
        raise typer.Exit(code=1)
    except ValueError as e:
        print_error("Invalid Input", str(e))
        raise typer.Exit(code=1)
    except ImportError as e:
        print_error("Import Error", str(e))
        typer.echo("   Tip: Check if your virtualenv is active.")
        raise typer.Exit(code=1)
    except Exception as e:
        print_error("Unexpected Error", f"An unhandled error occurred: {str(e)}")
        raise typer.Exit(code=1)


@app.command()
def init(
    complete: bool = typer.Option(
        False, "--complete", "-c", help="Generate a complete example with advanced features."
    ),
    no_config: bool = typer.Option(
        False, "--no-config", "-n", help="Skip generation of .teraconfig.toml."
    ),
) -> None:
    """
    Initializes a new Tera project with boilerplate files.
    """
    target_dir = Path.cwd()
    yaml_path = target_dir / "docs.yaml"

    if yaml_path.exists():
        typer.secho(f"⚠️  '{yaml_path.name}' already exists.", fg=typer.colors.YELLOW)
        if not typer.confirm("Do you want to overwrite it?"):
            typer.echo("Operation aborted.")
            raise typer.Exit()

    try:
        service = InitService()
        created_yaml, created_config = service.create_project(
            target_dir=target_dir,
            complete_mode=complete,
            skip_config=no_config,
        )

        typer.secho("\nProject initialized successfully!", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"   Created: {created_yaml.name}")
        if created_config:
            typer.echo(f"   Created: {created_config.name}")

        typer.secho("\nNext steps:", fg=typer.colors.BLUE)
        typer.echo("   1. Open docs.yaml and customize your API definition.")
        typer.echo("   2. Run 'tera lint docs.yaml' to validate.")
        typer.echo("   3. Run 'tera build' to generate OpenAPI specs.")
        typer.echo("")

    except Exception as e:
        print_error("Init Failed", str(e))
        raise typer.Exit(code=1)


@app.command()
def build(
    input_file: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the Tera YAML file. Default: docs.yaml",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to the output JSON/YAML (OpenAPI format).",
    ),
) -> None:
    """
    Reads a Tera YAML file and generates standard OpenAPI documentation.
    """
    typer.secho(f"Building OpenAPI from {input_file}...", fg=typer.colors.BLUE)

    config = loader.load_config()
    final_output = output_file or config.output or input_file.with_suffix(".json")

    _execute_pipeline(str(input_file), final_output, format_style="openapi")


@app.command()
def scan(
    app_id: Optional[str] = typer.Argument(
        None,
        help="Import string (e.g. 'main:app'). If empty, reads from .teraconfig.toml",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to the output Tera YAML file.",
    ),
) -> None:
    """
    Scans code and generates a canonical Tera YAML file (docs.yaml).
    """
    config = loader.load_config()
    final_target = app_id or config.target

    if not final_target:
        print_error(
            "Missing Target",
            "Please provide an app string (e.g., 'tera scan main:app') OR set 'target' in .teraconfig.toml",
        )
        raise typer.Exit(code=1)

    try:
        resolved_driver = factory.get_driver(final_target)
    except Exception:
        resolved_driver = None

    driver_labels: dict[str, str] = {
        "FlaskAppDriver": "Flask App",
        "FastApiDriver": "FastAPI App",
        "HarDriver": "HTTP Archive (HAR)",
        "PostmanCollectionDriver": "Postman Collection",
        "OpenApiDriver": "OpenAPI Specification",
        "YamlFileDriver": "Tera IR Specification",
        "GitFileDriver": "Git Revision",
        "HttpDriver": "Remote Specification",
    }
    label = (
        driver_labels.get(resolved_driver.__class__.__name__, resolved_driver.__class__.__name__)
        if resolved_driver is not None
        else "Application"
    )

    typer.secho(f"Scanning {label}: {final_target}...", fg=typer.colors.MAGENTA)

    final_output = output_file or config.output or Path("docs.yaml")
    _execute_pipeline(
        resolved_driver if resolved_driver is not None else final_target,
        final_output,
        format_style="tera",
        source_label=final_target,
    )


@app.command()
def export(
    input_file: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the Tera YAML file.",
    ),
    format: str = typer.Option(
        "markdown",
        "--format",
        "-f",
        help="Target format (markdown, html, postman).",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to the output file.",
    ),
) -> None:
    """
    Export documentation to external formats (Markdown, HTML, Postman).
    """
    valid_formats: dict[str, str] = {
        "markdown": ".md",
        "html": ".html",
        "postman": ".json",
    }
    if format not in valid_formats:
        print_error(
            "Invalid Format",
            f"Unknown format: '{format}'. Supported formats: markdown, html, postman.",
        )
        raise typer.Exit(code=1)

    typer.secho(f"Exporting to {format.upper()}...", fg=typer.colors.CYAN)

    final_output = output_file
    if not final_output:
        ext = valid_formats[format]
        final_output = input_file.with_suffix(ext)

    _execute_pipeline(
        str(input_file), final_output, format_style=cast(WriterFormatStyle, format)
    )



@app.command()
def lint(
    file_path: Path = typer.Argument(..., help="Path to the YAML/JSON file definition."),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output results as JSON (for CI/CD)."
    ),
) -> None:
    """
    Analyzes the documentation file for syntax errors, schema violations, and quality issues.
    """
    config = loader.load_config()
    service = LinterService(config=config)

    if not to_json:
        typer.secho(f"Linting '{file_path}'...", fg=typer.colors.BLUE)
        if config.lint.ignore:
            typer.secho(
                f"Ignoring rules: {', '.join(config.lint.ignore)}",
                fg=typer.colors.BRIGHT_BLACK,
            )

    issues = service.lint(file_path)
    present_lint_report(issues, as_json=to_json)

    has_errors = any(i.severity == LintSeverity.ERROR for i in issues)
    if has_errors:
        if not to_json:
            typer.secho("\nValidation failed with errors.", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)

    if not to_json:
        if issues:
            typer.secho("\n⚠️  Passed with warnings.", fg=typer.colors.YELLOW, bold=True)
        else:
            typer.secho("\n✅ No issues found. Good job!", fg=typer.colors.GREEN, bold=True)


@app.command()
def diff(
    base: str = typer.Argument(
        ..., help="Base schema file or git ref (e.g. docs.v1.yaml or HEAD~1:docs.yaml)."
    ),
    head: str = typer.Argument(
        "docs.yaml", help="Head schema file or git ref. Default: docs.yaml."
    ),
    to_json: bool = typer.Option(False, "--json", "-j", help="Output diff result as JSON."),
    fail_on_breaking: bool = typer.Option(
        False, "--fail-on-breaking", help="Exit with code 1 if breaking changes are detected."
    ),
    fail_on_drift: bool = typer.Option(
        False, "--fail-on-drift", help="Exit with code 1 if any difference is detected."
    ),
) -> None:
    """
    Compares two API specifications semantically and highlights breaking changes.
    """
    base_schema = _load_schema_or_exit(base, label="Base")
    head_schema = _load_schema_or_exit(head, label="Head")

    service = DiffService()
    schema_diff = service.compare(base_schema, head_schema)

    present_diff_report(schema_diff, base_ref=base, head_ref=head, as_json=to_json)

    if fail_on_drift and not schema_diff.is_empty:
        raise typer.Exit(code=1)

    if fail_on_breaking and schema_diff.has_breaking_changes:
        raise typer.Exit(code=1)


@app.command()
def semver(
    base: str = typer.Argument(
        ..., help="Base schema file or git ref (e.g. docs.v1.yaml or HEAD~1:docs.yaml)."
    ),
    head: str = typer.Argument(
        "docs.yaml", help="Head schema file or git ref. Default: docs.yaml."
    ),
    bump: bool = typer.Option(
        False, "--bump", "-b", help="Directly update 'api.version' in the head file on disk."
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output SemVer recommendation as JSON."
    ),
) -> None:
    """
    Analyzes API contract changes between two versions and suggests the SemVer bump.
    """
    base_schema = _load_schema_or_exit(base, label="Base")
    head_schema = _load_schema_or_exit(head, label="Head")

    diff_service = DiffService()
    schema_diff = diff_service.compare(base_schema, head_schema)

    semver_service = SemverService()
    result = semver_service.calculate_bump(schema_diff, head_schema.api.version)

    present_semver_report(result, base_ref=base, head_ref=head, as_json=to_json)

    if bump:
        head_path = Path(head)
        if not head_path.exists() or not head_path.is_file():
            print_error(
                "Cannot Bump Version",
                f"Target head '{head}' is not a writable file on disk.",
            )
            raise typer.Exit(code=1)

        try:
            semver_service.apply_bump(head_path, result.next_version)
            if not to_json:
                typer.secho(
                    f"✅ Updated '{head_path}' version to {result.next_version}\n",
                    fg=typer.colors.GREEN,
                    bold=True,
                )
        except Exception as e:
            print_error("Bump Failed", str(e))
            raise typer.Exit(code=1)


@app.command()
def changelog(
    base: str = typer.Argument(
        ..., help="Base schema file or git ref (e.g. docs.v1.yaml or HEAD~1:docs.yaml)."
    ),
    head: str = typer.Argument(
        "docs.yaml", help="Head schema file or git ref. Default: docs.yaml."
    ),
    version: Optional[str] = typer.Option(
        None, "--version", "-v", help="Release version. Default: version from head schema."
    ),
    release_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="Release date (YYYY-MM-DD). Default: today."
    ),
    output_file: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Write changelog markdown snippet to a file."
    ),
    append: bool = typer.Option(
        False,
        "--append",
        "-a",
        help="Prepend new release section into CHANGELOG.md in current directory.",
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output changelog section as JSON."
    ),
) -> None:
    """
    Generates Keep a Changelog markdown entries from semantic schema differences.
    """
    base_schema = _load_schema_or_exit(base, label="Base")
    head_schema = _load_schema_or_exit(head, label="Head")

    diff_service = DiffService()
    schema_diff = diff_service.compare(base_schema, head_schema)

    target_version = version or head_schema.api.version
    target_date = release_date or date.today().isoformat()

    changelog_service = ChangelogService()
    section = changelog_service.generate(
        schema_diff,
        version=target_version,
        release_date=target_date,
    )

    if to_json:
        print_json(section)
        return

    md_output = section.to_markdown()

    if output_file:
        try:
            output_file.write_text(md_output + "\n", encoding="utf-8")
            typer.secho(
                f"✅ Changelog written to '{output_file}'\n",
                fg=typer.colors.GREEN,
                bold=True,
            )
        except Exception as e:
            print_error("Write Error", f"Could not write to '{output_file}': {e}")
            raise typer.Exit(code=1)

    if append:
        changelog_path = Path("CHANGELOG.md")
        try:
            changelog_service.append_to_file(changelog_path, section)
            typer.secho(
                f"✅ Prepended release [{target_version}] into '{changelog_path}'\n",
                fg=typer.colors.GREEN,
                bold=True,
            )
        except Exception as e:
            print_error("Append Error", f"Could not update '{changelog_path}': {e}")
            raise typer.Exit(code=1)

    if not output_file and not append:
        typer.echo(md_output)


@app.command()
def sync(
    app_id: Optional[str] = typer.Argument(
        None,
        help="Import string (e.g. 'main:app'). If empty, reads 'target' from .teraconfig.toml",
    ),
    doc_file: Path = typer.Option(
        Path("docs.yaml"),
        "--doc",
        "-d",
        help="Path to the documentation file to synchronize. Default: docs.yaml",
    ),
    write: bool = typer.Option(
        False,
        "--write",
        "-w",
        help="Overwrite the documentation file with the synchronized schema.",
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help="Remove endpoints present in docs.yaml that are no longer present in code.",
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output sync result as JSON."
    ),
) -> None:
    """
    Self-healing synchronization: merges code AST reflection with existing documentation,
    updating technical structure while preserving human summaries, descriptions, and examples.
    """
    config = loader.load_config()
    final_target = app_id or config.target

    if not final_target:
        print_error(
            "Missing Target",
            "Please provide an app string (e.g. 'tera sync main:app') OR set 'target' in .teraconfig.toml",
        )
        raise typer.Exit(code=1)

    try:
        driver = factory.get_driver(final_target)
        code_schema = driver.load()
    except Exception as e:
        print_error("Code Scan Failed", str(e))
        raise typer.Exit(code=1)

    doc_schema = _load_schema_or_exit(doc_file, label="Doc File")

    service = SyncService()
    result = service.sync(code_schema, doc_schema, prune=prune)

    present_sync_report(
        result,
        target=final_target,
        doc_file=doc_file,
        write=write,
        as_json=to_json,
    )

    if write:
        try:
            writer = factory.get_writer(doc_file, format_style="tera")
            writer.write(result.merged_schema)
            typer.secho(
                f"✅ Successfully wrote synchronized schema to '{doc_file}'\n",
                fg=typer.colors.GREEN,
                bold=True,
            )
        except Exception as e:
            print_error("Write Error", f"Could not write synchronized schema: {e}")
            raise typer.Exit(code=1)


@app.command()
def coverage(
    file_path: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to analyze. Default: docs.yaml",
    ),
    min_coverage: Optional[float] = typer.Option(
        None,
        "--min-coverage",
        "-m",
        help="Minimum required coverage percentage (0-100). Fails with code 1 if below threshold.",
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output coverage report as JSON."
    ),
) -> None:
    """
    Analyzes API documentation completeness (summaries, descriptions, parameters, body fields, error responses).
    """
    schema = _load_schema_or_exit(file_path, label="File")

    service = CoverageService()
    report = service.calculate_coverage(schema)

    present_coverage_report(report, file_path=file_path, as_json=to_json)

    if min_coverage is not None and report.overall_score < min_coverage:
        if not to_json:
            typer.secho(
                f"❌ Coverage check failed: {report.overall_score}% is below required threshold of {min_coverage}%\n",
                fg=typer.colors.RED,
                bold=True,
            )
        raise typer.Exit(code=1)


@app.command()
def security(
    app_id: Optional[str] = typer.Argument(
        None,
        help="Import string (e.g. 'main:app'). If empty, reads 'target' from .teraconfig.toml",
    ),
    doc_file: Path = typer.Option(
        Path("docs.yaml"),
        "--doc",
        "-d",
        help="Path to the documentation file to audit. Default: docs.yaml",
    ),
    fail_on_drift: bool = typer.Option(
        False,
        "--fail-on-drift",
        help="Exit with code 1 if any security drift or discrepancy is detected.",
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output security drift report as JSON."
    ),
) -> None:
    """
    Audits security drift by comparing AST decorators in code against documentation auth contracts.
    """
    config = loader.load_config()
    final_target = app_id or config.target

    if not final_target:
        print_error(
            "Missing Target",
            "Please provide an app string (e.g. 'tera security main:app') OR set 'target' in .teraconfig.toml",
        )
        raise typer.Exit(code=1)

    try:
        driver = factory.get_driver(final_target)
        code_schema = driver.load()
    except Exception as e:
        print_error("Code Scan Failed", str(e))
        raise typer.Exit(code=1)

    doc_schema = _load_schema_or_exit(doc_file, label="Doc File")

    service = SecurityDriftService()
    report = service.audit(code_schema, doc_schema)

    present_security_report(
        report,
        target=final_target,
        doc_file=doc_file,
        as_json=to_json,
    )

    if fail_on_drift and report.has_drift:
        raise typer.Exit(code=1)


@app.command("import")
def import_spec(
    spec_file: Path = typer.Argument(
        ...,
        help="Path to the specification file (OpenAPI/Swagger, Postman Collection, or HAR) to import.",
    ),
    output: Path = typer.Option(
        Path("docs.yaml"),
        "--output",
        "-o",
        help="Destination path for the canonical Tera documentation file. Default: docs.yaml",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite output file if it already exists.",
    ),
    to_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output imported schema as JSON to stdout instead of saving to file.",
    ),
) -> None:
    """
    Imports an external specification (OpenAPI/Swagger, Postman Collection, or HAR) into canonical Tera IR (docs.yaml).
    """
    if not spec_file.exists():
        print_error("File Not Found", f"Specification file '{spec_file}' does not exist.")
        raise typer.Exit(code=1)

    try:
        driver = factory.get_driver(spec_file)
        if isinstance(driver, YamlFileDriver):
            driver = factory.get_driver(spec_file, driver_type="openapi")
        schema = driver.load()
    except TeraError as e:
        print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        print_error("Import Failed", f"Could not parse specification: {e}")
        raise typer.Exit(code=1)

    if to_json:
        print_json(schema)
        return

    if output.exists() and not force:
        print_error(
            "File Exists",
            f"The destination file '{output}' already exists. Use --force / -f to overwrite.",
        )
        raise typer.Exit(code=1)

    try:
        writer = factory.get_writer(output, format_style="tera")
        writer.write(schema)
        print_success(str(spec_file), str(output))
        typer.secho(
            f"Imported {len(schema.endpoints)} endpoints for '{schema.api.name}' (v{schema.api.version}).\n",
            fg=typer.colors.GREEN,
        )
    except Exception as e:
        print_error("Write Failed", f"Could not write to '{output}': {e}")
        raise typer.Exit(code=1)


@app.command()
def serve(
    doc_file: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to serve. Default: docs.yaml",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to run the HTTP documentation server on. Default: 8000",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host address to bind to. Default: 127.0.0.1",
    ),
    ui: str = typer.Option(
        "swagger",
        "--ui",
        help="Default interface: 'swagger' or 'redoc'. Default: swagger",
    ),
    open_browser: bool = typer.Option(
        False,
        "--open",
        "-b",
        help="Automatically open the documentation in the default web browser.",
    ),
) -> None:
    """
    Serves interactive API documentation (Swagger UI / Redoc) locally with live reloading.
    """
    if not doc_file.exists():
        print_error("File Not Found", f"Documentation file '{doc_file}' does not exist.")
        raise typer.Exit(code=1)

    ui_choice = ui.lower().strip()
    if ui_choice not in ("swagger", "redoc"):
        print_error("Invalid UI", "Option --ui must be either 'swagger' or 'redoc'.")
        raise typer.Exit(code=1)

    typer.echo("")
    typer.secho("🚀 Tera Documentation Server", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Documentation: {doc_file}")
    typer.echo(f"  Server URL:    http://{host}:{port}/")
    typer.echo(f"  Swagger UI:    http://{host}:{port}/swagger")
    typer.echo(f"  Redoc UI:      http://{host}:{port}/redoc")
    typer.echo(f"  OpenAPI Spec:  http://{host}:{port}/openapi.json")
    typer.secho(
        "\n  Watching for changes in documentation file... (Live refresh on browser reload)",
        fg=typer.colors.BRIGHT_BLACK,
    )
    typer.secho("  Press Ctrl+C to stop.\n", fg=typer.colors.YELLOW)

    try:
        run_server(
            file_path=doc_file,
            host=host,
            port=port,
            ui=ui_choice,
            open_browser=open_browser,
        )
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print_error("Server Error", str(e))
        raise typer.Exit(code=1)
    finally:
        typer.secho("\nServer stopped.", fg=typer.colors.GREEN)


@app.command()
def graph(
    doc_file: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to visualize. Default: docs.yaml",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to save the generated Mermaid diagram (e.g. graph.mmd or graph.md).",
    ),
    direction: str = typer.Option(
        "TD",
        "--direction",
        help="Graph direction: 'TD' (Top-Down) or 'LR' (Left-to-Right). Default: TD",
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output graph structure as JSON."
    ),
) -> None:
    """
    Generates a Mermaid dependency and architectural relationship graph from API endpoints.
    """
    schema = _load_schema_or_exit(doc_file, label="Doc File")

    dir_choice = direction.upper().strip()
    if dir_choice not in ("TD", "LR"):
        print_error("Invalid Direction", "Option --direction must be either 'TD' or 'LR'.")
        raise typer.Exit(code=1)

    service = GraphService()
    api_graph = service.build_graph(schema)

    if to_json:
        print_json(api_graph)
        return

    mermaid_code = api_graph.to_mermaid(direction=dir_choice)

    if output:
        try:
            if output.suffix.lower() == ".md":
                wrapped = f"```mermaid\n{mermaid_code}\n```\n"
                output.write_text(wrapped, encoding="utf-8")
            else:
                output.write_text(mermaid_code + "\n", encoding="utf-8")
            typer.secho(
                f"✅ Mermaid graph saved to '{output}' ({len(api_graph.nodes)} nodes, {len(api_graph.edges)} edges).\n",
                fg=typer.colors.GREEN,
                bold=True,
            )
        except Exception as e:
            print_error("Write Failed", f"Could not write to '{output}': {e}")
            raise typer.Exit(code=1)
    else:
        typer.echo(mermaid_code)


@app.command()
def audit(
    doc_file: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to audit. Default: docs.yaml",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit with code 1 if any CRITICAL or WARNING inconsistency is detected.",
    ),
    min_score: float = typer.Option(
        0.0,
        "--min-score",
        help="Minimum semantic coherence score (0-100) required to pass CI.",
    ),
    to_json: bool = typer.Option(
        False, "--json", "-j", help="Output audit report as JSON."
    ),
) -> None:
    """
    Audits semantic and structural consistency without LLMs (verb vs summary, status codes, path plurality, and public mutations).
    """
    schema = _load_schema_or_exit(doc_file, label="Doc File")

    service = AuditService()
    report = service.audit(schema)

    present_audit_report(report, doc_file=doc_file, as_json=to_json)

    failed = False
    if strict and (report.critical_count > 0 or report.warning_count > 0):
        typer.secho(
            "❌ Audit failed in strict mode: inconsistencies detected.\n",
            fg=typer.colors.RED,
            bold=True,
        )
        failed = True
    elif report.coherence_score < min_score:
        typer.secho(
            f"❌ Audit failed: Coherence score {report.coherence_score}% is below threshold {min_score}%.\n",
            fg=typer.colors.RED,
            bold=True,
        )
        failed = True

    if failed:
        raise typer.Exit(code=1)


@app.command("schema")
def schema_cmd(
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="File path to save the JSON Schema. If omitted, prints to stdout.",
    ),
    indent: int = typer.Option(
        2,
        "--indent",
        help="Indentation spaces for JSON output.",
    ),
) -> None:
    """
    Exports the JSON Schema for the canonical Tera IR (docs.yaml).
    """
    try:
        content = export_ir_json_schema(output_path=output_file, indent=indent)
        if output_file:
            typer.secho(f"\n✅ Tera IR schema exported to {output_file}", fg=typer.colors.GREEN, bold=True)
        else:
            typer.echo(content)
    except Exception as e:
        print_error("Schema Export Failed", str(e))
        raise typer.Exit(code=1)


@app.command("validate")
def validate_cmd(
    file_path: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to validate. Default: docs.yaml",
    ),
    to_json: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output validation result as JSON.",
    ),
) -> None:
    """
    Validates a docs.yaml specification against the canonical Tera IR schema.
    """
    service = ValidationService()
    report = service.validate(file_path)
    present_validation_report(report, as_json=to_json)

    if not report.is_valid:
        raise typer.Exit(code=1)