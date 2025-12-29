import typer
import json
from pathlib import Path
from pydantic import ValidationError
from .models.inputs import TeraSchema
from .core.converter import TeraConverter
from .core.reader import TeraReader
from .exceptions import TeraError, SchemaValidationError

app = typer.Typer(help="Tera CLI - Documentation Converter")

def print_error(title: str, message: str):
    """Prints generic errors in red."""
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)

def print_validation_error(errors: list):
    """Prints Pydantic errors formatted."""
    typer.secho(f"\n❌ Schema Validation Error:", fg=typer.colors.RED, bold=True)
    for err in errors:
        loc = " -> ".join([str(x) for x in err['loc']])
        msg = err['msg']
        typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)

def print_success(input_path: str, output_path: str):
    """Prints success message in green."""
    typer.secho("\n✅ Build successful!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Input:  {input_path}")
    typer.echo(f"   Output: {output_path}\n")

@app.command()
def build(
    input_file: Path = typer.Argument(
        "docs.yaml",
        help="Path to the YAML file. Default: docs.yaml"
    ),
    output_file: Path = typer.Option(
        None, 
        "--output", "-o", 
        help="Path to the output JSON. If omitted, uses the input filename."
    )
):
    """
    Main pipeline: Read -> Validate -> Convert -> Write
    """
    
    typer.secho(f"Starting build...", fg=typer.colors.BLUE)

    if not input_file.exists():
        print_error("File not found", f"The file '{input_file}' does not exist.")
        raise typer.Exit(code=1)
    
    if not input_file.is_file():
        print_error("Input Error", f"'{input_file}' is not a valid file.")
        raise typer.Exit(code=1)

    if not output_file:
        output_file = input_file.with_suffix('.json')

    try:
        # Reader Module
        raw_data = TeraReader.load(input_file)

        # Pydantic Models
        try:
            schema_model = TeraSchema(**raw_data)
        except ValidationError as e:
            raise SchemaValidationError(e.errors())

        # Converter Module
        converter = TeraConverter(schema_model)
        openapi_dict = converter.convert()

        # Write
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(openapi_dict, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print_error("Write Error", f"Could not save the file: {str(e)}")
            raise typer.Exit(code=1)

        print_success(str(input_file), str(output_file))

    # Centralized Error Handling
    except SchemaValidationError as e:
        print_validation_error(e.errors)
        raise typer.Exit(code=1)
        
    except TeraError as e:
        print_error(e.title, e.message)
        raise typer.Exit(code=1)
        
    except Exception as e:
        print_error("Unexpected Error", f"An unhandled error occurred: {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()