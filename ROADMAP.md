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

| Título | Descrição | Utilidade | Surpresa |

|---|---|---|---|

| Diff semântico entre versões | Compara duas árvores do `docs.yaml`, classifica mudanças (adição/remoção/tipo/obrigatoriedade) | 5 | 4 |
| Lint como CI gate (fail-on-drift) | Se o diff não for vazio no CI, quebra o build | 5 | 4 |
| Self-healing (PR automático) | Merge seguro dos campos estruturais + PR automático; campos semânticos ficam marcados `NEEDS REVIEW` pra humano decidir | 5 | 5 |
| Changelog automático | Gera entrada de CHANGELOG.md a partir do diff | 4 | 4 |
| Sugestão de semver | Sugere patch/minor/major com base no diff | 4 | 5 |
| Modo história da API (timeline) | `git log` + diff entre versões, virando timeline visual | 3 | 5 |

**Nota técnica do self-healing**: nunca sobrescrever tudo automaticamente. Separar campos **estruturais** (path, method, tipos/obrigatoriedade de parâmetros — vêm da AST, seguros pra auto-merge) de campos **semânticos** (summary, description, auth_required — podem ter intenção humana; marcar como pendente de revisão em vez de sobrescrever). Idempotência: sempre commitar na mesma branch (`tera/auto-sync`) com force-push, nunca criar branch nova a cada execução.

### Qualidade e estrutura (independentes do diff)

| Título | Descrição | Utilidade | Surpresa |

|---|---|---|---|

| Detector de drift de segurança | Cruza `auth_required` do IR com decorators reais do código | 5 | 5 |
| Doc coverage report | % de endpoints com descrição/exemplo/erros documentados | 4 | 4 |
| Grafo de dependência entre endpoints | AST detecta endpoints que compartilham modelo/se chamam; renderiza como Mermaid | 4 | 5 |
| Detector de inconsistência (sem LLM) | Regras estruturais: verbo do summary vs. method HTTP; status code vs. texto da descrição; singular/plural vs. tipo do example. **Não depende só de LLM** — cobre os erros mais comuns sem custo de API. | 4 | 3 |

### Entrada e saída (drivers/writers)

| Título | Descrição | Utilidade | Surpresa |

|---|---|---|---|

| Driver de import de OpenAPI existente | Lê `openapi.json/yaml` pronto, converte pro IR | 5 | 2 |
| `tera serve` | Embute Redoc/Swagger UI estático, serve local a partir do `docs.yaml` | 5 | 3 |

### Distribuição e adoção

| Título | Descrição | Utilidade | Surpresa |

|---|---|---|---|

| Pre-commit hook oficial | `tera lint` empacotado como hook | 3 | 2 |
| GitHub Action oficial | `uses: vichsort/tera-action@v1` roda lint/build em qualquer repo | 4 | 2 |
| Sistema de plugins via `entry_points` | Terceiros publicam drivers/writers como pacotes pip próprios | 4 | 3 |
| Faker nos exemplos | Troca exemplos genéricos por dados realistas via Faker | 3 | 3 |

---

## 5. Cortado do escopo (e por quê)

| Ideia | Motivo do corte |

|---|---|

| Fuzz/gerador de ataque a partir do schema | Schemathesis já faz isso, maduro e mantido |
| Mock server generator / contract test runner | Prism já faz os dois a partir de OpenAPI |
| Tradutor de doc pra outra stack / gerador de SDK | OpenAPI Generator já cobre dezenas de linguagens |
| `tera explain`, `tera roast`, detector semântico via LLM | Usuário pediu explicitamente: nada que dependa de LLM ou gere custo recorrente |
| Rastreador de "API zumbi" (cruzar com logs de acesso) | Válido, mas precisa de infra externa (acesso a logs) — não é "imediato" |
| Agregador multi-repo (portal único de docs) | Válido, mas precisa de portal hospedado — não é "imediato" |

---

## 6. Ordem sugerida de execução

1. [x] Checklist de fundação (seção 2) — base estabilizada, bugs corrigidos e modo strict de tipagem habilitado.
2. [x] `tera diff` (motor central) — comparação semântica entre versões, classificação de breaking changes e suporte a CI (`--fail-on-breaking`, `--fail-on-drift`).
3. [x] A partir do diff: `tera changelog` (concluído), `tera semver` (concluído), `tera sync` (self-healing concluído).
4. [x] Features independentes: `tera security` (detector de drift concluído), `tera coverage` (auditoria de completude concluída).
5. [x] Entrada & Visualização (Etapa 1): `tera import` (OpenApiDriver concluído), `tera serve` (servidor HTTP local Swagger UI/Redoc concluído).

---

*Gerado a partir de uma sessão de planejamento em 21/09/2026. Se algo aqui parecer desatualizado em relação ao código real, o código manda — este arquivo é só o mapa da conversa, não a fonte de verdade do projeto.*
