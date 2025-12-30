import typer
from pathlib import Path
from pydantic import ValidationError
from tera.core import factory
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

def _execute_pipeline(input_source: str, output_path: Path):
    """
    Helper function to execute the pipeline safely.
    Connects: Factory -> Pipeline -> UI
    """
    try:
        driver = factory.get_driver(input_source)
        writer = factory.get_writer(output_path)

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
        help="Path to the YAML file. Default: docs.yaml"
    ),
    output_file: Path = typer.Option(
        None, 
        "--output", "-o", 
        help="Path to the output JSON/YAML."
    )
):
    """Build documentation from a YAML file."""
    typer.secho(f"Building from YAML...", fg=typer.colors.BLUE)
    
    if not output_file:
        output_file = input_file.with_suffix('.json')

    _execute_pipeline(str(input_file), output_file)


@app.command()
def scan(
    app_id: str = typer.Argument(
        ...,
        help="Import string of the Flask app (e.g. 'main:app')"
    ),
    output_file: Path = typer.Option(
        "docs.yaml", 
        "--output", "-o",
        help="Path to the output file."
    )
):
    """Scan a Flask application code and auto-generate documentation skeleton."""
    typer.secho(f"Scanning Flask App: {app_id}...", fg=typer.colors.MAGENTA)

    _execute_pipeline(app_id, output_file)