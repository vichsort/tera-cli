# tera-cli
!!!!!!Ainda não é o README final!!!!!!!!  
Apenas explicações para uma compreensão sobre a estrutura e abstração de tarefas. Isso deve me ajudar a manter o código limpo e organizado (se eu tiver sorte de lembrar hahaha)

```
├── 📁 tera
│   ├── 📁 adapters
│   │   └── 🐍 openapi.py
│   ├── 📁 contracts
│   │   ├── 🐍 drivers.py
│   │   └── 🐍 writers.py
│   ├── 📁 domain
│   │   └── 🐍 models.py
│   ├── 📁 drivers
│   │   └── 🐍 yaml_driver.py
│   ├── 📁 services
│   │   └── 🐍 pipeline.py
│   ├── 📁 writers
│   │   └── 🐍 json_writer.py
│   ├── 🐍 exceptions.py
│   └── 🐍 main.py
├── 📁 tests
│   ├── 📁 integration
│   │   ├── 🐍 test_cli.py
│   │   └── 🐍 test_default_file.py
│   ├── 📁 unit
│   │   └── 🐍 test_converter.py
│   └── 🐍 conftest.py
├── ⚙️ .gitignore
├── 📝 README.md
└── 📄 requirements.txt
```
## Estrutura Tera
A estrutura visa separar ao máximo o sistema de entrada e saída, permitindo mudar QUALQUER COISA em QUALQUER LUGAR sem obrigando uma refatoração ou transformação total. Assim, separei cada trecho de lógica para que permita replicabilidade, escalabilidade ou modificação futura. Repare na estrutura e a separação de responsabilidade.

### Domain
Coração do sistema. Contém o TeraSchema e as definições do que é uma API, um Endpoint, etc. Ele não sabe ler arquivos, não sabe o que é JSON e não sabe o que é Typer. Ele apenas define a estrutura de dados válida do sistema usando Pydantic.

### Contracts
Regras e protocolos de o que o sistema deve fazer (mas não como fazer)
- `drivers.py`: Define que "todo Driver deve ter um método load()".
- `writers.py`: Define que "todo Writer deve ter um método write()".
Assim todo sistema depende que haja input e output, mas a forma é indiferente, permitindo eu mudar de item ingerido ou de forma que vai ser mandado o final.

### Drivers
Porta de entrada. Por enquanto tem só yaml, mas dá pra gente ver de colocar algo a mais... Como planejo ter um scanner junto, aqui vai ter ele - já que é uma ENTRADA.

### Services
Serviços que nem todo sistema tem, mas no nosso caso são tipo maestros, que lidam com a forma que todo o sistema vai agir. Aqui tem a camada de aplicação (ou mais ou menos) que é o pipeline -> junta ***i** no **o** (driver/writer) sem saber o que exatamente faz, apenas realiza a ação, indiferente se vai ler yaml ou json e transformar em json ou yaml.

### Adapters
Traduzem os nossos schemas pro dicionário que queremos (nesse momento OpenAPI 3.0). Ele encapsula a lógica do negócio e envia pro responsável.

### Writers
Mecanismos de output. Pega o resultado do adapter e efetivamente grava no disco.

## Futuro:
- Leitura de api
- Scan
- 'build'
- Documentação
- Mais testes
- Deploy