class TeraError(Exception):
    """Classe base para todas as exceções do Tera CLI."""
    def __init__(self, title: str, message: str):
        self.title = title
        self.message = message
        super().__init__(f"{title}: {message}")

class YamlSyntaxError(TeraError):
    """Erro lançado quando o YAML está mal formatado."""
    pass

class SchemaValidationError(TeraError):
    """Erro lançado quando o Pydantic rejeita os dados."""
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__("Erro de Validação", "O arquivo não segue o schema esperado.")

class FileLoadError(TeraError):
    """Erro ao tentar abrir ou ler o arquivo."""
    pass