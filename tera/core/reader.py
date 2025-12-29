import yaml
from pathlib import Path
from typing import Dict, Any
from ..exceptions import FileLoadError, YamlSyntaxError

class TeraReader:
    @staticmethod
    def load(file_path: Path) -> Dict[str, Any]:
        """
        Lê um arquivo YAML e retorna um dicionário cru.
        Lança exceções customizadas em caso de erro.
        """
        if not file_path.exists():
            raise FileLoadError("Arquivo Inexistente", f"O caminho '{file_path}' não foi encontrado.")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = yaml.safe_load(f)
                
            if content is None:
                raise FileLoadError("Arquivo Vazio", "O arquivo existe mas não tem conteúdo.")
                
            return content

        except yaml.YAMLError as e:
            # pega o erro técnico do PyYAML e transforma num erro amigável nosso
            erro_msg = str(e)
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                erro_msg = f"Erro na linha {mark.line + 1}, coluna {mark.column + 1}"
            
            raise YamlSyntaxError("Sintaxe Inválida", erro_msg)
            
        except Exception as e:
            raise FileLoadError("Erro de Leitura", str(e))