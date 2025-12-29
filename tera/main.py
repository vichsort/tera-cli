import typer
import yaml
import json
from pathlib import Path
from pydantic import ValidationError
from .models.inputs import TeraSchema
from .core.converter import TeraConverter

app = typer.Typer(help="Tera CLI - Conversor de Documentação")

def print_error(title: str, message: str):
    """Helper para mensagens de erro consistentes"""
    typer.secho(f"\n❌ {title}", fg=typer.colors.RED, bold=True)
    typer.secho(f"   {message}", fg=typer.colors.RED)

def print_success(input_path: str, output_path: str):
    """Helper para mensagem de sucesso"""
    typer.secho("\n✅ Build concluído com sucesso!", fg=typer.colors.GREEN, bold=True)
    typer.echo(f"   Entrada: {input_path}")
    typer.echo(f"   Saída:  {output_path}\n")

@app.command()
def build(
    input_file: Path = typer.Argument(
        ..., 
        exists=True, 
        file_okay=True, 
        readable=True, 
        help="Caminho do arquivo YAML de entrada"
    ),
    output_file: Path = typer.Option(
        None, 
        "--output", "-o", 
        help="Caminho de saída do JSON"
    )
):
    """
    Compila um arquivo Tera YAML para OpenAPI JSON.
    """
    typer.secho(f"Iniciando build...", fg=typer.colors.BLUE)
    
    # output
    if not output_file:
        output_file = input_file.with_suffix('.json')

    # ler e Validar YAML
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
        
        if not raw_data:
            print_error("Erro de Leitura", "O arquivo está vazio.")
            raise typer.Exit(code=1)

        # Validação Pydantic
        schema_model = TeraSchema(**raw_data)
            
    except yaml.YAMLError as e:
        print_error("Erro de Sintaxe YAML", str(e))
        raise typer.Exit(code=1)
        
    except ValidationError as e:
        typer.secho(f"\nErro de Validação no Schema:", fg=typer.colors.RED, bold=True)
        for err in e.errors():
            loc = " -> ".join([str(x) for x in err['loc']])
            msg = err['msg']
            typer.secho(f"   {loc}: {msg}", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    # convertemos
    try:
        converter = TeraConverter(schema_model)
        openapi_dict = converter.convert()
            
    except Exception as e:
        print_error("Erro Interno", f"Falha na conversão: {str(e)}")
        raise typer.Exit(code=1)

    # Salvar Arquivo
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(openapi_dict, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print_error("Erro de Gravação", f"Não foi possível salvar o arquivo: {str(e)}")
        raise typer.Exit(code=1)

    # Sucesso
    print_success(str(input_file), str(output_file))

if __name__ == "__main__":
    app()