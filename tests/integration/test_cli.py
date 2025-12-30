import textwrap
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()

def test_build_command_happy_path(tmp_path):
    """
    Cria um arquivo YAML temporário real, roda o build e verifica se o JSON nasceu.
    """
    d = tmp_path / "subdir"
    d.mkdir()
    input_file = d / "input.yaml"
    output_file = d / "output.json"
    
    input_content = textwrap.dedent("""
    api:
      name: Integration Test
      version: "1.0"
      auth:
        type: bearer
    endpoints:
      - path: /ping
        method: GET
        summary: Ping
        responses:
          success:
            example: { "pong": true }
    """)
    
    input_file.write_text(input_content, encoding="utf-8")

    result = runner.invoke(app, [str(input_file), "-o", str(output_file)])

    if result.exit_code != 0:
        print("\n--- DEBUG TYPER OUTPUT ---")
        print(result.output)
        print("--------------------------")

    assert result.exit_code == 0
    assert "✅ Build successful!" in result.output
    assert output_file.exists()

def test_build_file_not_found():
    """Testa se o sistema falha quando o arquivo não existe."""
    result = runner.invoke(app, ["ghost_file.yaml"])
    
    assert result.exit_code != 0

    assert "does not exist" in result.output