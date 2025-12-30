import typer
from pathlib import Path
from pydantic import ValidationError
from tera.drivers.yaml_driver import YamlFileDriver
from tera.writers.json_writer import JsonFileWriter
from tera.services.pipeline import run_pipeline
from tera.exceptions import TeraError, SchemaValidationError

app = typer.Typer(help="Tera CLI - Documentation Converter")

# --- UI Helpers ---
def print_error(title: str, message: str):
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)

def print_validation_error(e: ValidationError):
    typer.secho(f"\n❌ Schema Validation Error:", fg=typer.colors.RED, bold=True)
    for err in e.errors():
        loc = " -> ".join([str(x) for x in err['loc']])
        msg = err['msg']
        typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)

def print_success(input_path: str, output_path: str):
    typer.secho("\n✅ Build successful!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Input:  {input_path}")
    typer.echo(f"   Output: {output_path}\n")

# --- Main Command ---
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
    Main pipeline using Hexagonal Architecture.
    Driver (YAML) -> Domain -> Adapter (OpenAPI) -> Writer (JSON)
    """
    typer.secho(f"Starting build...", fg=typer.colors.BLUE)
    
    # 1. Output Path Logic
    if not output_file:
        output_file = input_file.with_suffix('.json')

    try:
        # --- A Mágica da Injeção de Dependência ---
        
        # Instanciamos o Driver (Quem lê)
        # Note: A validação de "arquivo existe" agora pertence ao Driver!
        driver = YamlFileDriver(input_file)
        
        # Instanciamos o Writer (Quem escreve)
        writer = JsonFileWriter(output_file)
        
        # Executamos o Pipeline
        run_pipeline(driver, writer)

        # ------------------------------------------

        print_success(str(input_file), str(output_file))

    # Tratamento de Erros
    except SchemaValidationError as e:
        print_validation_error(e.errors)
        raise typer.Exit(code=1)
        
    except TeraError as e:
        print_error(e.title, e.message)
        raise typer.Exit(code=1)
        
    except Exception as e:
        print_error("Unexpected Error", f"An unhandled error occurred: {str(e)}")
        raise typer.Exit(code=1)

    except Exception as e:
        print_error("Unexpected Error", f"An unhandled error occurred: {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()