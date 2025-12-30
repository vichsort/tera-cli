import typer
from pathlib import Path
from pydantic import ValidationError
from tera.drivers.yaml_driver import YamlFileDriver
from tera.drivers.flask_driver import FlaskAppDriver
from tera.writers.json_writer import JsonFileWriter
from tera.writers.yaml_writer import YamlFileWriter
from tera.services.pipeline import run_pipeline
from tera.contracts.drivers import TeraDriver
from tera.contracts.writers import TeraWriter

app = typer.Typer(help="Tera CLI - Documentation Converter")

def print_error(title: str, message: str):
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)

def print_validation_error(e: ValidationError):
    typer.secho(f"\n❌ Schema Validation Error:", fg=typer.colors.RED, bold=True)
    for err in e.errors():
        loc = " -> ".join([str(x) for x in err['loc']])
        msg = err['msg']
        typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)

def print_success(input_ref: str, output_path: str):
    typer.secho("\n✅ Operation successful!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Input:  {input_ref}")
    typer.echo(f"   Output: {output_path}\n")

def _get_writer_for_file(path: Path) -> TeraWriter:
    """Decides wich writer to use based on file extension."""
    if path.suffix in ['.yaml', '.yml']:
        return YamlFileWriter(path)
    return JsonFileWriter(path)

def _execute_safe(driver: TeraDriver, writer: TeraWriter, input_ref: str, output_path: str):
    """Centralized wrapper to execute the pipeline with error handling."""
    try:
        run_pipeline(driver, writer)
        print_success(input_ref, output_path)

    except ValidationError as e:
        print_validation_error(e)
        raise typer.Exit(code=1)

    except FileNotFoundError as e:
        print_error("File Error", str(e))
        raise typer.Exit(code=1)

    except ImportError as e:
        print_error("Import Error", str(e))
        typer.echo("   Tip: Check if your virtualenv is active and the file exists.")
        raise typer.Exit(code=1)

    except ValueError as e:
        print_error("Value Error", str(e))
        raise typer.Exit(code=1)

    except Exception as e:
        print_error("Unexpected Error", f"An unhandled error occurred: {str(e)}")
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

    driver = YamlFileDriver(input_file)
    writer = _get_writer_for_file(output_file)

    _execute_safe(driver, writer, str(input_file), str(output_file))


@app.command()
def scan(
    app_id: str = typer.Argument(
        ...,
        help="Import string of the Flask app (e.g. 'main:app')"
    ),
    output_file: Path = typer.Option(
        "docs.yaml",
        "--output", "-o",
        help="Path to the output file (YAML recommended for editing)."
    )
):
    """Scan a Flask application code and auto-generate documentation skeleton."""
    typer.secho(f"Scanning Flask App: {app_id}...", fg=typer.colors.MAGENTA)

    driver = FlaskAppDriver(app_id)
    writer = _get_writer_for_file(output_file)

    _execute_safe(driver, writer, app_id, str(output_file))

if __name__ == "__main__":
    app()