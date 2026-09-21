import typer
import json
from typing import Optional, cast
from pathlib import Path
from pydantic import ValidationError
from tera.core import factory, loader
from tera.core.factory import WriterFormatStyle
from tera.services import (
    run_pipeline, 
    InitService, 
    LinterService, 
    DiffService, 
    load_schema_from_source, 
    SemverService,
    ChangelogService,
    SyncService,
    CoverageService,
    SecurityDriftService,
    run_server
)
from tera.exceptions import TeraError
from tera.domain import LintSeverity, LintIssue, SchemaDiff, SemverResult

app = typer.Typer(help="Tera CLI - Documentation Converter")

def _print_error(title: str, message: str) -> None:
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)

def _print_success(input_ref: str, output_path: str) -> None:
    typer.secho("\n✅ Operation successful!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Input:  {input_ref}")
    typer.echo(f"   Output: {output_path}\n")

def _print_validation_error(e: ValidationError) -> None:
    typer.secho(f"\n❌ Schema Validation Error:", fg=typer.colors.RED, bold=True)
    for err in e.errors():
        loc = " -> ".join([str(x) for x in err['loc']])
        msg = err['msg']
        typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)

def _print_human_lint_report(issues: list[LintIssue]) -> None:
    """Renders colored output for cli"""
    if not issues:
        return

    typer.echo("")
    for issue in issues:
        if issue.severity == LintSeverity.ERROR:
            color = typer.colors.RED
            icon = "❌"
            label = "ERROR"
        else:
            color = typer.colors.YELLOW
            icon = "⚠️ "
            label = "WARN "

        loc_str = f"[{issue.location}] " if issue.location else ""
        line_str = f"(Line {issue.line}) " if issue.line else ""

        message = f"{icon}  {label}  {issue.message}"
        meta = f"    Source: {loc_str}{line_str}| Code: {issue.code}"
        
        typer.secho(message, fg=color, bold=True)
        typer.secho(meta, fg=typer.colors.BRIGHT_BLACK)
        typer.echo("")

def _print_json_lint_report(issues: list[LintIssue]) -> None:
    """Renders output as JSON for cli"""
    output = [issue.model_dump() for issue in issues]
    typer.echo(json.dumps(output, indent=2))

def _print_diff_human_report(diff: SchemaDiff, base_ref: str, head_ref: str) -> None:
    """Renders human-readable colored diff report for the CLI."""
    typer.echo("")
    typer.secho(f"Comparing '{base_ref}' -> '{head_ref}'\n", bold=True)

    if diff.is_empty:
        typer.secho("✅ No differences detected. Specifications are identical.", fg=typer.colors.GREEN, bold=True)
        typer.echo("")
        return

    if diff.api_changes:
        typer.secho("API Metadata:", fg=typer.colors.CYAN, bold=True)
        for change in diff.api_changes:
            icon = "+" if change.kind == "added" else ("-" if change.kind == "removed" else "~")
            color = typer.colors.RED if change.impact == "breaking" else (typer.colors.GREEN if change.kind == "added" else typer.colors.YELLOW)
            breaking_tag = " [BREAKING]" if change.impact == "breaking" else ""
            typer.secho(f"  {icon} {change.path}{breaking_tag}: {change.description}", fg=color)
        typer.echo("")

    if diff.endpoint_diffs:
        typer.secho("Endpoints:", fg=typer.colors.CYAN, bold=True)
        for ep in diff.endpoint_diffs:
            if ep.kind == "added":
                typer.secho(f"  + {ep.method} {ep.path} (added)", fg=typer.colors.GREEN, bold=True)
            elif ep.kind == "removed":
                typer.secho(f"  - {ep.method} {ep.path} [BREAKING] (removed)", fg=typer.colors.RED, bold=True)
            else:
                ep_breaking = " [BREAKING]" if ep.impact == "breaking" else ""
                ep_color = typer.colors.RED if ep.impact == "breaking" else typer.colors.YELLOW
                typer.secho(f"  ~ {ep.method} {ep.path}{ep_breaking}", fg=ep_color, bold=True)
                for c in ep.changes:
                    c_icon = "+" if c.kind == "added" else ("-" if c.kind == "removed" else "~")
                    c_breaking = " [BREAKING]" if c.impact == "breaking" else ""
                    c_color = typer.colors.RED if c.impact == "breaking" else (typer.colors.GREEN if c.kind == "added" else typer.colors.YELLOW)
                    typer.secho(f"      {c_icon} {c.description}{c_breaking}", fg=c_color)
        typer.echo("")

    breaking_str = f"{diff.breaking_count} breaking" if diff.breaking_count > 0 else "0 breaking"
    summary_color = typer.colors.RED if diff.has_breaking_changes else typer.colors.GREEN
    typer.secho(f"Summary: {diff.total_changes} change(s) ({breaking_str})", fg=summary_color, bold=True)
    typer.echo("")

def _print_semver_human_report(result: SemverResult, base_ref: str, head_ref: str) -> None:
    """Renders human-readable SemVer recommendation report."""
    typer.echo("")
    typer.secho(f"SemVer Analysis: '{base_ref}' -> '{head_ref}'\n", bold=True)

    typer.echo(f"  Current Version:  {result.current_version}")

    bump_color = typer.colors.GREEN
    if result.bump == "major":
        bump_color = typer.colors.RED
    elif result.bump == "minor":
        bump_color = typer.colors.BLUE
    elif result.bump == "patch":
        bump_color = typer.colors.YELLOW

    typer.secho(f"  Recommended Bump: {result.bump.upper()}", fg=bump_color, bold=True)
    typer.secho(f"  Next Version:     {result.next_version}", fg=typer.colors.GREEN, bold=True)
    typer.echo("")

    if result.reasons:
        typer.secho("Justification:", fg=typer.colors.CYAN, bold=True)
        for reason in result.reasons:
            if "breaking" in reason.lower():
                typer.secho(f"  - {reason}", fg=typer.colors.RED)
            elif "added" in reason.lower() or "feature" in reason.lower():
                typer.secho(f"  - {reason}", fg=typer.colors.GREEN)
            else:
                typer.secho(f"  - {reason}", fg=typer.colors.BRIGHT_BLACK)
        typer.echo("")

def _execute_pipeline(input_source: str, output_path: Path, format_style: WriterFormatStyle = 'tera') -> None:
    """
    Helper function to execute the pipeline safely.
    Connects: Factory -> Pipeline -> UI
    """
    try:
        driver = factory.get_driver(input_source)
        writer = factory.get_writer(output_path, format_style=format_style)

        run_pipeline(driver, writer)
        _print_success(input_source, str(output_path))

    except ValidationError as e:
        _print_validation_error(e)
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        _print_error("File Not Found", str(e))
        raise typer.Exit(code=1)
    except ValueError as e:
        _print_error("Invalid Input", str(e))
        raise typer.Exit(code=1)
    except ImportError as e:
        _print_error("Import Error", str(e))
        typer.echo("   Tip: Check if your virtualenv is active.")
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Unexpected Error", f"An unhandled error occurred: {str(e)}")
        raise typer.Exit(code=1)

@app.command()
def init(
    complete: bool = typer.Option(False, "--complete", "-c", help="Generate a complete example with advanced features."),
    no_config: bool = typer.Option(False, "--no-config", "-n", help="Skip generation of .teraconfig.toml.")
):
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
            skip_config=no_config
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
        _print_error("Init Failed", str(e))
        raise typer.Exit(code=1)

@app.command()
def build(
    input_file: Path = typer.Argument(
        "docs.yaml",
        help="Path to the Tera YAML file. Default: docs.yaml"
    ),
    output_file: Optional[Path] = typer.Option(
        None, 
        "--output", "-o",
        help="Path to the output JSON/YAML (OpenAPI format)."
    )
):
    """
    Reads a Tera YAML file and generates standard OpenAPI documentation.
    """
    typer.secho(f"Building OpenAPI from {input_file}...", fg=typer.colors.BLUE)
    
    config = loader.load_config()
    final_output = output_file or config.output or input_file.with_suffix('.json')

    _execute_pipeline(str(input_file), final_output, format_style='openapi')


@app.command()
def scan(
    app_id: Optional[str] = typer.Argument(
        None,
        help="Import string (e.g. 'main:app'). If empty, reads from .teraconfig.toml"
    ),
    output_file: Optional[Path] = typer.Option(
        None, 
        "--output", "-o",
        help="Path to the output Tera YAML file."
    )
):
    """
    Scans code and generates a canonical Tera YAML file (docs.yaml).
    """
    config = loader.load_config()
    final_target = app_id or config.target
    
    if not final_target:
        _print_error(
            "Missing Target", 
            "Please provide an app string (e.g., 'tera scan main:app') OR set 'target' in .teraconfig.toml"
        )
        raise typer.Exit(code=1)

    typer.secho(f"Scanning Flask App: {final_target}...", fg=typer.colors.MAGENTA)

    final_output = output_file or config.output or Path("docs.yaml")

    _execute_pipeline(final_target, final_output, format_style='tera')

@app.command()
def export(
    input_file: Path = typer.Argument(
        "docs.yaml",
        help="Path to the Tera YAML file."
    ),
    format: str = typer.Option(
        "markdown",
        "--format", "-f",
        help="Target format (markdown, html, postman)."
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Path to the output file."
    )
):
    """
    Export documentation to external formats (Markdown, HTML, Postman).
    """
    valid_formats: dict[str, str] = {
        'markdown': '.md',
        'html': '.html',
        'postman': '.json'
    }
    if format not in valid_formats:
        _print_error("Invalid Format", f"Unknown format: '{format}'. Supported formats: markdown, html, postman.")
        raise typer.Exit(code=1)

    typer.secho(f"Exporting to {format.upper()}...", fg=typer.colors.CYAN)

    if not output_file:
        ext = valid_formats[format]
        output_file = input_file.with_suffix(ext)

    _execute_pipeline(str(input_file), output_file, format_style=cast(WriterFormatStyle, format))

@app.command()
def lint(
    file_path: Path = typer.Argument(..., help="Path to the YAML/JSON file definition."),
    to_json: bool = typer.Option(False, "--json", "-j", help="Output results as JSON (for CI/CD).")
):
    """
    Analyzes the documentation file for syntax errors, schema violations, and quality issues.
    """
    config = loader.load_config()
    service = LinterService(config=config)
    
    if not to_json:
        typer.secho(f"Linting '{file_path}'...", fg=typer.colors.BLUE)
        if config.lint.ignore:
            typer.secho(f"Ignoring rules: {', '.join(config.lint.ignore)}", fg=typer.colors.BRIGHT_BLACK)
    
    issues = service.lint(file_path)

    if to_json:
        _print_json_lint_report(issues)
    else:
        _print_human_lint_report(issues)

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
    base: str = typer.Argument(..., help="Base schema file or git ref (e.g. docs.v1.yaml or HEAD~1:docs.yaml)."),
    head: str = typer.Argument("docs.yaml", help="Head schema file or git ref. Default: docs.yaml."),
    to_json: bool = typer.Option(False, "--json", "-j", help="Output diff result as JSON."),
    fail_on_breaking: bool = typer.Option(False, "--fail-on-breaking", help="Exit with code 1 if breaking changes are detected."),
    fail_on_drift: bool = typer.Option(False, "--fail-on-drift", help="Exit with code 1 if any difference is detected.")
) -> None:
    """
    Compares two API specifications semantically and highlights breaking changes.
    """
    try:
        base_schema = load_schema_from_source(base)
    except FileNotFoundError as e:
        _print_error("Base Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Base", str(e))
        raise typer.Exit(code=1)

    try:
        head_schema = load_schema_from_source(head)
    except FileNotFoundError as e:
        _print_error("Head Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Head", str(e))
        raise typer.Exit(code=1)

    service = DiffService()
    schema_diff = service.compare(base_schema, head_schema)

    if to_json:
        typer.echo(json.dumps(schema_diff.model_dump(), indent=2))
    else:
        _print_diff_human_report(schema_diff, base, head)

    if fail_on_drift and not schema_diff.is_empty:
        raise typer.Exit(code=1)

    if fail_on_breaking and schema_diff.has_breaking_changes:
        raise typer.Exit(code=1)

@app.command()
def semver(
    base: str = typer.Argument(..., help="Base schema file or git ref (e.g. docs.v1.yaml or HEAD~1:docs.yaml)."),
    head: str = typer.Argument("docs.yaml", help="Head schema file or git ref. Default: docs.yaml."),
    bump: bool = typer.Option(False, "--bump", "-b", help="Directly update 'api.version' in the head file on disk."),
    to_json: bool = typer.Option(False, "--json", "-j", help="Output SemVer recommendation as JSON.")
) -> None:
    """
    Analyzes changes between specifications and suggests the next semantic version (MAJOR, MINOR, PATCH).
    """
    try:
        base_schema = load_schema_from_source(base)
    except FileNotFoundError as e:
        _print_error("Base Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Base", str(e))
        raise typer.Exit(code=1)

    try:
        head_schema = load_schema_from_source(head)
    except FileNotFoundError as e:
        _print_error("Head Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Head", str(e))
        raise typer.Exit(code=1)

    diff_service = DiffService()
    schema_diff = diff_service.compare(base_schema, head_schema)

    semver_service = SemverService()
    result = semver_service.calculate_bump(schema_diff, head_schema.api.version)

    if to_json:
        typer.echo(json.dumps(result.model_dump(), indent=2))
    else:
        _print_semver_human_report(result, base, head)

    if bump:
        head_path = Path(head)
        if not head_path.exists() or not head_path.is_file():
            _print_error("Cannot Bump Version", f"Target head '{head}' is not a writable file on disk.")
            raise typer.Exit(code=1)

        try:
            semver_service.apply_bump(head_path, result.next_version)
            if not to_json:
                typer.secho(f"✅ Updated '{head_path}' version to {result.next_version}\n", fg=typer.colors.GREEN, bold=True)
        except Exception as e:
            _print_error("Bump Failed", str(e))
            raise typer.Exit(code=1)

@app.command()
def changelog(
    base: str = typer.Argument(..., help="Base schema file or git ref (e.g. docs.v1.yaml or HEAD~1:docs.yaml)."),
    head: str = typer.Argument("docs.yaml", help="Head schema file or git ref. Default: docs.yaml."),
    version: Optional[str] = typer.Option(None, "--version", "-v", help="Release version. Default: version from head schema."),
    release_date: Optional[str] = typer.Option(None, "--date", "-d", help="Release date (YYYY-MM-DD). Default: today."),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Write changelog markdown snippet to a file."),
    append: bool = typer.Option(False, "--append", "-a", help="Prepend new release section into CHANGELOG.md in current directory."),
    to_json: bool = typer.Option(False, "--json", "-j", help="Output changelog section as JSON.")
) -> None:
    """
    Generates Keep a Changelog markdown entries from semantic schema differences.
    """
    try:
        base_schema = load_schema_from_source(base)
    except FileNotFoundError as e:
        _print_error("Base Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Base", str(e))
        raise typer.Exit(code=1)

    try:
        head_schema = load_schema_from_source(head)
    except FileNotFoundError as e:
        _print_error("Head Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Head", str(e))
        raise typer.Exit(code=1)

    diff_service = DiffService()
    schema_diff = diff_service.compare(base_schema, head_schema)

    target_version = version or head_schema.api.version

    changelog_service = ChangelogService()
    section = changelog_service.generate(schema_diff, version=target_version, release_date=release_date)

    if to_json:
        typer.echo(json.dumps(section.model_dump(), indent=2))
        return

    md_output = section.to_markdown()

    if output_file:
        try:
            output_file.write_text(md_output + "\n", encoding="utf-8")
            typer.secho(f"✅ Changelog written to '{output_file}'\n", fg=typer.colors.GREEN, bold=True)
        except Exception as e:
            _print_error("Write Error", f"Could not write to '{output_file}': {e}")
            raise typer.Exit(code=1)

    if append:
        changelog_path = Path("CHANGELOG.md")
        try:
            changelog_service.append_to_file(changelog_path, section)
            typer.secho(f"✅ Prepended release [{target_version}] into '{changelog_path}'\n", fg=typer.colors.GREEN, bold=True)
        except Exception as e:
            _print_error("Append Error", f"Could not update '{changelog_path}': {e}")
            raise typer.Exit(code=1)

    if not output_file and not append:
        typer.echo(md_output)

@app.command()
def sync(
    app_id: Optional[str] = typer.Argument(
        None,
        help="Import string (e.g. 'main:app'). If empty, reads 'target' from .teraconfig.toml"
    ),
    doc_file: Path = typer.Option(
        Path("docs.yaml"),
        "--doc", "-d",
        help="Path to the documentation file to synchronize. Default: docs.yaml"
    ),
    write: bool = typer.Option(
        False,
        "--write", "-w",
        help="Overwrite the documentation file with the synchronized schema."
    ),
    prune: bool = typer.Option(
        False,
        "--prune",
        help="Remove endpoints present in docs.yaml that are no longer present in code."
    ),
    to_json: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output sync result as JSON."
    )
) -> None:
    """
    Self-healing synchronization: merges code AST reflection with existing documentation,
    updating technical structure while preserving human summaries, descriptions, and examples.
    """
    config = loader.load_config()
    final_target = app_id or config.target

    if not final_target:
        _print_error(
            "Missing Target",
            "Please provide an app string (e.g. 'tera sync main:app') OR set 'target' in .teraconfig.toml"
        )
        raise typer.Exit(code=1)

    try:
        driver = factory.get_driver(final_target)
        code_schema = driver.load()
    except Exception as e:
        _print_error("Code Scan Failed", str(e))
        raise typer.Exit(code=1)

    try:
        doc_schema = load_schema_from_source(doc_file)
    except FileNotFoundError as e:
        _print_error("Doc File Not Found", str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Doc File", str(e))
        raise typer.Exit(code=1)

    service = SyncService()
    result = service.sync(code_schema, doc_schema, prune=prune)

    if to_json:
        typer.echo(json.dumps(result.model_dump(), indent=2))
        return

    typer.echo("")
    typer.secho("🔄 Self-Healing Sync Report", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Code target:       {final_target}")
    typer.echo(f"  Doc specification: {doc_file}")
    typer.echo("")

    if result.endpoints_added:
        typer.secho(f"  + {len(result.endpoints_added)} endpoint(s) added from code:", fg=typer.colors.GREEN, bold=True)
        for ep in result.endpoints_added:
            typer.secho(f"      + {ep}", fg=typer.colors.GREEN)
        typer.echo("")

    if result.endpoints_updated:
        typer.secho(f"  ~ {len(result.endpoints_updated)} endpoint(s) updated structurally:", fg=typer.colors.YELLOW, bold=True)
        for ep in result.endpoints_updated:
            typer.secho(f"      ~ {ep}", fg=typer.colors.YELLOW)
        typer.echo("")

    if result.endpoints_orphaned:
        typer.secho(f"  ⚠️  {len(result.endpoints_orphaned)} orphaned endpoint(s) missing from code (retained):", fg=typer.colors.MAGENTA, bold=True)
        for ep in result.endpoints_orphaned:
            typer.secho(f"      ? {ep}", fg=typer.colors.MAGENTA)
        typer.echo("      Tip: run with --prune to remove orphaned endpoints.")
        typer.echo("")

    if result.endpoints_pruned:
        typer.secho(f"  - {len(result.endpoints_pruned)} orphaned endpoint(s) pruned:", fg=typer.colors.RED, bold=True)
        for ep in result.endpoints_pruned:
            typer.secho(f"      - {ep}", fg=typer.colors.RED)
        typer.echo("")

    typer.secho(f"  ✓ {result.annotations_preserved} human annotation(s) preserved.", fg=typer.colors.CYAN, bold=True)
    typer.echo("")

    if write:
        try:
            writer = factory.get_writer(doc_file, format_style='tera')
            writer.write(result.merged_schema)
            typer.secho(f"✅ Successfully wrote synchronized schema to '{doc_file}'\n", fg=typer.colors.GREEN, bold=True)
        except Exception as e:
            _print_error("Write Error", f"Could not write synchronized schema: {e}")
            raise typer.Exit(code=1)
    else:
        typer.secho("ℹ️  Dry-run complete. Run with --write (-w) to update the file.\n", fg=typer.colors.BRIGHT_BLACK)

@app.command()
def coverage(
    file_path: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to analyze. Default: docs.yaml"
    ),
    min_coverage: Optional[float] = typer.Option(
        None,
        "--min-coverage", "-m",
        help="Minimum required coverage percentage (0-100). Fails with code 1 if below threshold."
    ),
    to_json: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output coverage report as JSON."
    )
) -> None:
    """
    Analyzes API documentation completeness (summaries, descriptions, parameters, body fields, error responses).
    """
    try:
        schema = load_schema_from_source(file_path)
    except FileNotFoundError as e:
        _print_error("File Not Found", str(e))
        raise typer.Exit(code=1)
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Specification", str(e))
        raise typer.Exit(code=1)

    service = CoverageService()
    report = service.calculate_coverage(schema)

    if to_json:
        typer.echo(json.dumps(report.model_dump(), indent=2))
    else:
        typer.echo("")
        typer.secho(f"📊 Documentation Coverage Report: '{file_path}'", fg=typer.colors.BLUE, bold=True)
        typer.echo(f"  Analyzed {report.total_endpoints} endpoint(s)\n")

        for ep in report.endpoints:
            score_color = typer.colors.GREEN if ep.score >= 80 else (typer.colors.YELLOW if ep.score >= 50 else typer.colors.RED)
            typer.secho(f"  {ep.method} {ep.path} — {ep.score}%", fg=score_color, bold=True)
            for missing in ep.missing_items:
                typer.secho(f"    - {missing}", fg=typer.colors.BRIGHT_BLACK)

        typer.echo("")
        typer.secho("Summary Stats:", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"  Summaries documented:       {report.summaries_score}%")
        typer.echo(f"  Descriptions documented:    {report.descriptions_score}%")
        typer.echo(f"  Parameters documented:      {report.params_score}%")
        typer.echo(f"  Body fields documented:     {report.body_score}%")
        typer.echo(f"  Error responses documented: {report.errors_score}%")
        typer.echo("")

        overall_color = typer.colors.GREEN if report.overall_score >= 80 else (typer.colors.YELLOW if report.overall_score >= 50 else typer.colors.RED)
        typer.secho(f"Overall Documentation Coverage: {report.overall_score}%\n", fg=overall_color, bold=True)

    if min_coverage is not None and report.overall_score < min_coverage:
        if not to_json:
            typer.secho(
                f"❌ Coverage check failed: {report.overall_score}% is below required threshold of {min_coverage}%\n",
                fg=typer.colors.RED,
                bold=True
            )
        raise typer.Exit(code=1)

@app.command()
def security(
    app_id: Optional[str] = typer.Argument(
        None,
        help="Import string (e.g. 'main:app'). If empty, reads 'target' from .teraconfig.toml"
    ),
    doc_file: Path = typer.Option(
        Path("docs.yaml"),
        "--doc", "-d",
        help="Path to the documentation file to audit. Default: docs.yaml"
    ),
    fail_on_drift: bool = typer.Option(
        False,
        "--fail-on-drift",
        help="Exit with code 1 if any security drift or discrepancy is detected."
    ),
    to_json: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output security drift report as JSON."
    )
) -> None:
    """
    Audits security drift by comparing AST decorators in code against documentation auth contracts.
    """
    config = loader.load_config()
    final_target = app_id or config.target

    if not final_target:
        _print_error(
            "Missing Target",
            "Please provide an app string (e.g. 'tera security main:app') OR set 'target' in .teraconfig.toml"
        )
        raise typer.Exit(code=1)

    try:
        driver = factory.get_driver(final_target)
        code_schema = driver.load()
    except Exception as e:
        _print_error("Code Scan Failed", str(e))
        raise typer.Exit(code=1)

    try:
        doc_schema = load_schema_from_source(doc_file)
    except FileNotFoundError as e:
        _print_error("Doc File Not Found", str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Error Loading Doc File", str(e))
        raise typer.Exit(code=1)

    service = SecurityDriftService()
    report = service.audit(code_schema, doc_schema)

    if to_json:
        typer.echo(json.dumps(report.model_dump(), indent=2))
    else:
        typer.echo("")
        typer.secho("🛡️  Security Drift Audit Report", fg=typer.colors.BLUE, bold=True)
        typer.echo(f"  Code target:       {final_target}")
        typer.echo(f"  Doc specification: {doc_file}\n")

        if not report.has_drift:
            typer.secho("  ✅ No security drift detected. Code decorators match documentation auth contracts.\n", fg=typer.colors.GREEN, bold=True)
        else:
            for issue in report.issues:
                severity_color = typer.colors.RED if issue.severity == "CRITICAL" else typer.colors.YELLOW
                typer.secho(f"  [{issue.severity}] {issue.method} {issue.path}", fg=severity_color, bold=True)
                typer.secho(f"     {issue.description}", fg=typer.colors.BRIGHT_BLACK)

            typer.echo("")
            summary_color = typer.colors.RED if report.critical_count > 0 else typer.colors.YELLOW
            typer.secho(
                f"Summary: {report.critical_count} critical issue(s), {report.warning_count} warning(s)\n",
                fg=summary_color,
                bold=True
            )

    if fail_on_drift and report.has_drift:
        raise typer.Exit(code=1)

@app.command("import")
def import_spec(
    spec_file: Path = typer.Argument(
        ...,
        help="Path to the OpenAPI (3.0/3.1) or Swagger (2.0) file (.json or .yaml) to import."
    ),
    output: Path = typer.Option(
        Path("docs.yaml"),
        "--output", "-o",
        help="Destination path for the canonical Tera documentation file. Default: docs.yaml"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Overwrite output file if it already exists."
    ),
    to_json: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output imported schema as JSON to stdout instead of saving to file."
    )
) -> None:
    """
    Imports an existing OpenAPI/Swagger specification (JSON or YAML) into the canonical Tera IR (docs.yaml).
    """
    if not spec_file.exists():
        _print_error("File Not Found", f"OpenAPI specification '{spec_file}' does not exist.")
        raise typer.Exit(code=1)

    try:
        driver = factory.get_driver(spec_file, driver_type="openapi")
        schema = driver.load()
    except TeraError as e:
        _print_error(e.title, e.message)
        raise typer.Exit(code=1)
    except Exception as e:
        _print_error("Import Failed", f"Could not parse OpenAPI specification: {e}")
        raise typer.Exit(code=1)

    if to_json:
        typer.echo(json.dumps(schema.model_dump(), indent=2))
        return

    if output.exists() and not force:
        _print_error(
            "File Exists",
            f"The destination file '{output}' already exists. Use --force / -f to overwrite."
        )
        raise typer.Exit(code=1)

    try:
        writer = factory.get_writer(output, format_style="tera")
        writer.write(schema)
        _print_success(str(spec_file), str(output))
        typer.secho(
            f"Imported {len(schema.endpoints)} endpoints for '{schema.api.name}' (v{schema.api.version}).\n",
            fg=typer.colors.GREEN
        )
    except Exception as e:
        _print_error("Write Failed", f"Could not write to '{output}': {e}")
        raise typer.Exit(code=1)

@app.command()
def serve(
    doc_file: Path = typer.Argument(
        Path("docs.yaml"),
        help="Path to the documentation file to serve. Default: docs.yaml"
    ),
    port: int = typer.Option(
        8000,
        "--port", "-p",
        help="Port to run the HTTP documentation server on. Default: 8000"
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host", "-h",
        help="Host address to bind to. Default: 127.0.0.1"
    ),
    ui: str = typer.Option(
        "swagger",
        "--ui",
        help="Default interface: 'swagger' or 'redoc'. Default: swagger"
    ),
    open_browser: bool = typer.Option(
        False,
        "--open", "-b",
        help="Automatically open the documentation in the default web browser."
    )
) -> None:
    """
    Serves interactive API documentation (Swagger UI / Redoc) locally with live reloading.
    """
    if not doc_file.exists():
        _print_error("File Not Found", f"Documentation file '{doc_file}' does not exist.")
        raise typer.Exit(code=1)

    ui_choice = ui.lower().strip()
    if ui_choice not in ("swagger", "redoc"):
        _print_error("Invalid UI", "Option --ui must be either 'swagger' or 'redoc'.")
        raise typer.Exit(code=1)

    typer.echo("")
    typer.secho("🚀 Tera Documentation Server", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Documentation: {doc_file}")
    typer.echo(f"  Server URL:    http://{host}:{port}/")
    typer.echo(f"  Swagger UI:    http://{host}:{port}/swagger")
    typer.echo(f"  Redoc UI:      http://{host}:{port}/redoc")
    typer.echo(f"  OpenAPI Spec:  http://{host}:{port}/openapi.json")
    typer.secho("\n  Watching for changes in documentation file... (Live refresh on browser reload)", fg=typer.colors.BRIGHT_BLACK)
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
        _print_error("Server Error", str(e))
        raise typer.Exit(code=1)
    finally:
        typer.secho("\nServer stopped.", fg=typer.colors.GREEN)