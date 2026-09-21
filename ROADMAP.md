# tera-cli — Notas de retomada

> Resumo de uma sessão de planejamento sobre o projeto [tera-cli](https://github.com/vichsort/tera-cli).
> Objetivo do projeto: virar o "golden example" de portfólio do autor.
> Cole este arquivo numa conversa nova com o Claude pra continuar exatamente daqui, sem precisar re-explicar tudo.

---

## 1. Estado atual (verificado rodando o código, não só lendo)

- 16 commits, de 29/12/2025 a 01/01/2026 — parado há ~8 meses e meio.
- Arquitetura em camadas já bem separada: `domain` (Pydantic), `contracts` (Protocols: `TeraDriver`, `TeraWriter`, `TeraLinter`), `drivers` (entrada: YAML e Flask via AST), `core` (factory/config/loader), `services` (pipeline, init, linter), `writers` (json, yaml, markdown, html, openapi, postman).
- `tera/services/pipeline.py` é praticamente um diagrama de Clean Architecture em 4 linhas — ponto forte a preservar.
- Comandos testados e funcionando de ponta a ponta: `init`, `scan` (reflection AST em Flask, incluindo detecção de body via Pydantic), `build`, `lint` (já tem saída `--json` pensada pra CI), `export` (markdown/html/postman).
- README está desatualizado (descreve uma estrutura mais simples e antiga; não menciona `scan`, `lint` nem `export`).

### Bugs concretos encontrados (arquivo + linha)

1. **`tera/drivers/flask_driver.py`, linhas ~118–126**: `_extract_pydantic_fields` calcula `prop_type` certo (a partir do JSON Schema do Pydantic) mas **nunca passa `type=prop_type`** pro `BodyField(...)`. Resultado: todo campo sai com `type: string`, mesmo quando é int/bool/etc. O mesmo padrão de bug (falta `type=`) acontece no `ParamField(...)` dos path params (linhas ~62–67).
2. **`tera/core/factory.py`**: `get_writer` declara `format_style: Literal['tera', 'openapi']`, mas a função aceita `'markdown'`, `'html'` e `'postman'` também. `mypy`/`pyright` vai acusar erro nas chamadas reais.
3. **`tera/cli/commands.py`**, dentro do comando `lint`: sobrou um comentário órfão em português (`# 3. Executa... (o resto continua igual)`) — resíduo de edição anterior.
4. **Testes quebrados**: 3 de 7 testes falham. Um refactor do `main.py` (commit "clean main.py file...") mudou o CLI pra estrutura de subcomandos do Typer, mas os testes antigos ainda esperam que `tera` sem argumento nenhum já rode `build` com `docs.yaml` por padrão.
5. **`requirements.txt` e `pyproject.toml` duplicam exatamente as mesmas 21 dependências** — risco de um ficar desatualizado em relação ao outro.
6. **Sem `LICENSE`, sem CI** (`.github/workflows` não existe).
7. Docstrings misturam português e inglês; typos em contratos públicos (`TeraWriter.write`: "Recieves a shcema"; `BaseField`: "Essencial content of data"); `ResponseSuccess.description` tem `"Sucesso"` hardcoded como default.
8. `BaseField.type` no domínio (`tera/domain/models.py`) é um `str` solto — deveria ser um `Literal`/Enum fechado com os tipos válidos de JSON Schema, o que teria evitado o bug #1 de forma estrutural.
9. **Templates não empacotados (`package-data`)**: `tera/templates/` (`*.yaml`, `*.toml`, `*.j2`) não estão declarados em `[tool.setuptools.package-data]`. O build de wheel/sdist ignora esses arquivos, causando `FileNotFoundError` em runtime (`tera init`, `tera export --format html`).
10. **Dependências travadas com `==` e tooling de teste em runtime**: `pyproject.toml` trava versões exatas (`==`), o que causa conflitos ao ser instalado como dependência; ferramentas de desenvolvimento (`pytest`, `iniconfig`, `pluggy`, `packaging`) estão em `dependencies` principais em vez de `[project.optional-dependencies]`.
11. **Metadados de distribuição ausentes no `pyproject.toml`**: Faltam `readme`, `license`, `requires-python`, `classifiers` e `urls` essenciais para publicação no PyPI.

---

## 2. Checklist de fundação (fazer ANTES de qualquer feature nova)

- [x] Corrigir os 2 bugs de tipo (`flask_driver.py`, `factory.py`)
- [x] Resolver os 3 testes quebrados (decidir: restaurar comportamento antigo do CLI ou atualizar os testes)
- [x] Adicionar `LICENSE` (MIT é o padrão razoável aqui) + workflow de GitHub Actions rodando `pytest`
- [x] Configurar empacotamento correto no `pyproject.toml` (declarar `package-data` para `templates/*`)
- [x] Consolidar e flexibilizar dependências no `pyproject.toml` (remover pins exatos `==`, mover `pytest` para `optional-dependencies`, remover `requirements.txt` redundante)
- [x] Completar metadados de distribuição no `pyproject.toml` (`readme`, `license`, `requires-python`, `classifiers`, `urls`)
- [x] Padronizar idioma (inglês em código/docstrings; português, se quiser, só nas mensagens da CLI) e limpar resíduos/typos
- [x] Trocar `type: str` solto por `Literal` fechado em `BaseField`
- [x] Atualizar o README pra refletir a estrutura e os comandos atuais

---

## 3. Posicionamento estratégico

**A ideia central da sessão**: o diferencial do tera **não é** "escanear Flask via AST" — isso já existe (ByteDocs Flask faz reflection parecida). O diferencial real é o **IR (`docs.yaml`) como formato canônico intermediário**, desacoplado de entrada e saída — um hub N-pra-1-pra-M, não um conversor direto código→doc.

```text
Flask (scan) ─┐                    ┌─→ OpenAPI json (build)
FastAPI (*)  ─┼─→  docs.yaml (IR) ─┼─→ Markdown (export)
OpenAPI (*)  ─┤                    ├─→ HTML/Redoc (export)
escrito à mão ┘                    └─→ Postman collection (export)

```

`(*)` = drivers que ainda não existem, mas o padrão `contracts/drivers/writers` já suporta.

Pra virar "produto" de verdade (não só arquitetura interna):

1. Congelar/versionar o schema publicamente ("Tera IR v1"), com um `tera validate`.
2. Deixar claro que dá pra **escrever** o `docs.yaml` à mão, não só gerar via scan.
3. Publicar o JSON Schema do IR separado do código Python.

### Ferramentas maduras que já existem — não reinventar

Pesquisado e confirmado durante a sessão:

- **Schemathesis**: fuzzing/property-based testing a partir de schema OpenAPI. Já maduro (usado por Netflix/SAP/IBM).
- **Prism (Stoplight)**: mock server *e* contract testing a partir de OpenAPI.
- **OpenAPI Generator**: gera client SDK e server stub em dezenas de linguagens a partir de OpenAPI.
- **Postman CLI**: não é concorrente — ele opera sobre uma collection/spec que você já tem, não lê código-fonte. É um passo *depois* do tera, não substituto.

**Conclusão**: o papel do tera é gerar um IR/OpenAPI bom o suficiente pra alimentar essas ferramentas — não competir com elas.

---

## 4. Features — tabela final (pós-corte)

### Motor central (tudo nasce do diff semântico entre versões do IR)

| Título | Descrição | Status |
|---|---|---|
| Diff semântico entre versões (`tera diff`) | Compara duas árvores do `docs.yaml`, classifica mudanças (adição/remoção/tipo/obrigatoriedade) e breaking changes | Concluído (`[x]`) |
| Lint como CI gate (fail-on-drift) | Suporte a `--fail-on-drift` e `--fail-on-breaking` no CLI | Concluído (`[x]`) |
| Self-healing (`tera sync`) | Merge seguro de campos estruturais da AST preservando anotações humanas (`description`, `example`), com `--write` e `--prune` | Concluído (`[x]`) |
| Changelog automático (`tera changelog`) | Gera release notes no formato Keep a Changelog a partir do diff, com exportação e append | Concluído (`[x]`) |
| Sugestão de semver (`tera semver`) | Sugere patch/minor/major com base no diff estrutural e aplica bump no `docs.yaml` via `--bump` | Concluído (`[x]`) |

### Qualidade e estrutura (independentes do diff)

| Título | Descrição | Status |
|---|---|---|
| Detector de drift de segurança (`tera security`) | Cruza `auth_required` da documentação com decorators reais do código Flask (`@jwt_required`, `@login_required`), com flag `--fail-on-drift` | Concluído (`[x]`) |
| Doc coverage report (`tera coverage`) | % de endpoints com summaries, descrições, parâmetros, body e erros documentados, com gating `--min-coverage` | Concluído (`[x]`) |
| Grafo de dependência entre endpoints (`tera graph`) | Constrói grafo de dependência arquitetural (CRUD lifecycle, sub-recursos, hierarquia) e exporta em Mermaid (`flowchart TD/LR`) | Concluído (`[x]`) |
| Auditoria de inconsistências semânticas (`tera audit`) | Regras determinísticas sem LLM (`INC001` a `INC004`), score percentual de coerência e modo `--strict` para CI | Concluído (`[x]`) |

### Entrada e saída (drivers/writers)

| Título | Descrição | Status |
|---|---|---|
| Driver de import de OpenAPI existente (`tera import`) | Lê `openapi.json/yaml` (OpenAPI 3.0/3.1 e Swagger 2.0) e converte pro IR canônico `docs.yaml` | Concluído (`[x]`) |
| Servidor de documentação local (`tera serve`) | Servidor HTTP nativo servindo Swagger UI e Redoc com hot-reload automático por `mtime` | Concluído (`[x]`) |
| Driver de revisões Git (`GitFileDriver`) | Carrega especificações diretamente do histórico Git (`git:HEAD~1:docs.yaml`, `HEAD:spec.json`) com suporte a OpenAPI | Concluído (`[x]`) |
| `FastApiDriver` (Tier 1) | Ingestão nativa de apps FastAPI via `app.openapi()` sem dependência direta do framework | Concluído (`[x]`) |
| `HttpDriver` (Tier 1) | Leitura remota de specs (OpenAPI, docs.yaml, Postman) via `http://` e `https://` com auth | Concluído (`[x]`) |
| `PostmanCollectionDriver` (Tier 1) | Ingestão multi-versão de coleções Postman (v1.0, v2.0, v2.1, v3) com normalizer pattern | Concluído (`[x]`) |
| `HarDriver` (Tier 1) | Engenharia reversa de tráfego HTTP Archive (.har) com normalização heurística de rotas dinâmicas | Concluído (`[x]`) |

---

## 5. Refatoração e Padronização Arquitetural (DRY & SOLID)

Executada em 3 etapas cirúrgicas para consolidar a escalabilidade do projeto:

1. **Etapa 1: Enriquecimento do Domínio & Unificação de `BaseField`**:
   - `EndpointParams`: propriedade `all_params` unificando parâmetros.
   - `Endpoint`: validador para normalização de métodos HTTP (`GET`), propriedades `key` e `identifier`.
   - `TeraSchema`: índice `endpoint_map` e método de busca `get_endpoint`.
   - Unificação da mesclagem de coleções de campos (`_merge_field_list`) no `SyncService` e da comparação de campos (`_compare_fields`) no `DiffService`.

2. **Etapa 2: Unificação de Drivers e Ingestão (`TeraDriver`)**:
   - Criação do `GitFileDriver` sob o contrato `TeraDriver` para histórico Git.
   - Padronização de `YamlFileDriver` (alias `TeraFileDriver`) para carregar YAML e JSON via `FileLoader`.
   - Desambiguação centralizada na fábrica `get_driver` (OpenAPI, Flask, Tera e Git).
   - Redução de `load_schema_from_source` para fachada de ~20 linhas.

3. **Etapa 3: Desacoplamento da Apresentação CLI & Padronização de Erros**:
   - Criação de `tera/cli/presenters.py` isolando 100% da renderização visual de terminal, cores, formatação e JSON (SRP).
   - Redução de `tera/cli/commands.py` de 1.052 para ~540 linhas.
   - Helper `_load_schema_or_exit` eliminando mais de 150 linhas de blocos `try/except` idênticos.

---

## 6. Estado Atual de Validação e Qualidade

- **Suíte de Testes**: 201 testes automatizados (unitários e de integração), 100% passando em ~1.7s.
- **Tipagem Estrita**: Pyright configurado no modo `strict` com 0 erros e 0 warnings.
- **Clean Architecture**: Domínio desacoplado de frameworks de apresentação e infraestrutura externa.

---

## 7. Arquitetura de Extensibilidade & Plugins (Estratégia 3 Tiers)

Adoção do princípio *Batteries-Included, Extensible via Plugins* para preservar DevX sem fragmentação por micro-pacotes:

1. **Tier 1 — Core "Zero-Install" (Embutido)**:
   - Funciona imediatamente via `pip install tera-cli`, sem downloads adicionais.
   - Formatos: OpenAPI, YAML/JSON canônico, Git, HTTP/HTTPS, Postman (v1/v2/v3), HAR, Flask, FastAPI.
2. **Tier 2 — Extras Oficiais (Lazy Dependencies)**:
   - Dependências pesadas gerenciadas no monorepo e instaladas sob demanda (`pip install "tera-cli[django]"`).
3. **Tier 3 — Plugins Externos / Enterprise (Escape Hatch)**:
   - Descoberta via `importlib.metadata.entry_points(group="tera.plugins")` e configuração de scripts locais via `tera.toml`.
   - Permite drivers corporativos proprietários e regras de linting customizadas sem forkar o projeto.

---

## 8. Próximos Passos (Extensibilidade, Drivers & Ecossistema)

1. [x] **Refatoração do Core**: Substituir `factory.py` por `DriverRegistry` e `WriterRegistry` unificados.
2. [x] **`FastApiDriver`**: Ingestão de instâncias FastAPI via `app.openapi()` e auto-detecção em `module:attr`.
3. [x] **`HttpDriver`**: Ingestão de especificações remotas via HTTP/HTTPS com suporte a headers de autenticação.
4. [x] **`PostmanCollectionDriver`**: Normalizer multi-versão suportando schemas v1.0, v2.0, v2.1 e v3.
5. [x] **`HarDriver`**: Parser de arquivos `.har` com colapso heurístico de rotas dinâmicas (`/users/{id}`) e inferência de payload.
6. [x] **Sistema de Plugins via Entry Points (Tier 3)**: Descoberta dinâmica de extensões via grupo `tera.plugins`.
7. [x] **Suporte a Plugins Locais**: Carregamento de extensões locais declaradas no `tera.toml`.
8. [ ] **Pre-commit hook oficial**: Empacotar `tera lint` como hook do `pre-commit`.
9. [ ] **GitHub Action oficial**: Criar action (`uses: vichsort/tera-action@v1`) para CI gates.
