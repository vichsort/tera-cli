import typer
from typing import Optional
from pathlib import Path
from pydantic import ValidationError
from tera.core import factory, loader
from tera.services import run_pipeline
from tera.exceptions import TeraError

app = typer.Typer(help="Tera CLI - Documentation Converter")

def _print_error(title: str, message: str):
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)

def _print_success(input_ref: str, output_path: str):
    typer.secho("\n✅ Operation successful!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Input:  {input_ref}")
    typer.echo(f"   Output: {output_path}\n")

def _print_validation_error(e: ValidationError):
    typer.secho(f"\n❌ Schema Validation Error:", fg=typer.colors.RED, bold=True)
    for err in e.errors():
        loc = " -> ".join([str(x) for x in err['loc']])
        msg = err['msg']
        typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)

def _execute_pipeline(input_source: str, output_path: Path, format_style: str = 'tera'):
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
    typer.secho(f"Exporting to {format.upper()}...", fg=typer.colors.CYAN)

    if not output_file:
        extension_map = {
            'markdown': '.md',
            'html': '.html',
            'postman': '.json'
        }

        ext = extension_map.get(format, '.txt')
        output_file = input_file.with_suffix(ext)

    _execute_pipeline(str(input_file), output_file, format_style=format)