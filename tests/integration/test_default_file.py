import textwrap
import os
from typer.testing import CliRunner
from tera.main import app

runner = CliRunner()

def test_build_uses_default_docs_yaml():
    """
    Testa se rodar o comando sem argumentos busca o 'docs.yaml' na pasta atual.
    """
    with runner.isolated_filesystem():
        with open("docs.yaml", "w", encoding="utf-8") as f:
            f.write(textwrap.dedent("""
            api:
              name: Default Test
              version: "1.0"
            endpoints:
              - path: /
                method: GET
                summary: Home
                responses:
                  success:
                    example: { "ok": true }
            """))

        result = runner.invoke(app, []) 

        if result.exit_code != 0:
            print("\n--- TYPER ERROR OUTPUT ---")
            print(result.output)
            print("--------------------------")

        assert result.exit_code == 0, "Command failed using default docs.yaml"

        assert "docs.yaml" in result.output
        assert "Build successful" in result.output

        assert os.path.exists("docs.json")