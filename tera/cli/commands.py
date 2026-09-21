import typer
import json
from typing import Optional, cast
from pathlib import Path
from pydantic import ValidationError
from tera.core import factory, loader
from tera.core.factory import WriterFormatStyle
from tera.services import run_pipeline, InitService, LinterService, DiffService, load_schema_from_source
from tera.exceptions import TeraError
from tera.domain import LintSeverity, LintIssue, SchemaDiff

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