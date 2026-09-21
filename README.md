# tera-cli

> **Documentation as Code Tool** — Canonical Intermediate Representation (IR) Hub for API Specifications.

`tera-cli` is a developer-centric CLI designed to decouple API documentation inputs from outputs. Instead of translating directly from code to documentation, `tera` uses a canonical intermediate representation (`docs.yaml`) that can be scanned from code, written by hand, linted in CI, and exported into multiple formats.

```text
Flask App (scan) ─┐                    ┌─→ OpenAPI 3.0 (build)
FastAPI (*)      ─┼─→  docs.yaml (IR) ─┼─→ Markdown Documentation (export)
OpenAPI spec (*) ─┤                    ├─→ Interactive HTML / Redoc (export)
Handcrafted YAML ─┘                    └─→ Postman Collection (export)
```

---

## Architecture

Built with Clean Architecture principles and strict layer isolation:

- **`domain`**: Pydantic models defining the canonical schema (`TeraSchema`, `Endpoint`, `ParamField`, `BodyField`). Completely agnostic of I/O, CLI, or serialization formats.
- **`contracts`**: Python `Protocol` definitions (`TeraDriver`, `TeraWriter`, `TeraLinter`) enforcing input/output contracts.
- **`drivers`**: Input ingestion layers:
  - `YamlFileDriver`: Parses `docs.yaml` definitions into `TeraSchema`.
  - `FlaskAppDriver`: AST static analysis and introspection of Flask routes, docstrings, security decorators, and Pydantic models.
- **`adapters`**: Schema transformations (e.g., `TeraOpenApiAdapter` converting canonical schemas into OpenAPI 3.0.3 structures).
- **`writers`**: Output format implementations:
  - `JsonFileWriter`, `YamlFileWriter`: Tera IR outputs.
  - `OpenApiJsonWriter`, `OpenApiYamlWriter`: OpenAPI 3.0 specs.
  - `MarkdownWriter`: Human-readable markdown docs.
  - `HtmlWriter`: Standalone Redoc HTML documentation.
  - `PostmanWriter`: Postman Collection v2.1.
- **`services`**: Core orchestration pipelines:
  - `run_pipeline(driver, writer)`: Execution orchestrator.
  - `InitService`: Project boilerplate generation.
  - `LinterService`: Static syntax, schema, and semantic rule enforcement.
  - `DiffService`: Semantic schema comparison and breaking change detection.
  - `SemverService`: Semantic version recommendation and version bumping.
  - `ChangelogService`: Automated Keep a Changelog generator.
  - `SyncService`: Self-healing synchronization merging AST reflection with human docs.
  - `CoverageService`: Documentation completeness and metric reporting.
  - `SecurityDriftService`: Security decorator auditing and drift detection.
- **`cli`**: Subcommands powered by Typer.

---

## Installation

### From Source

```bash
git clone https://github.com/vichsort/tera-cli.git
cd tera-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Commands

### 1. `init`

Scaffolds a new documentation project with sample definitions and configuration.

```bash
tera init
# Or generate an advanced boilerplate:
tera init --complete
```

### 2. `scan`

Extracts API schemas directly from application source code using AST and introspection without starting a live server.

```bash
tera scan my_app:app -o docs.yaml
```

### 3. `build`

Compiles canonical `docs.yaml` into OpenAPI 3.0 specification.

```bash
tera build docs.yaml -o openapi.json
```

### 4. `lint`

Performs static analysis on documentation definitions to ensure completeness, validity, and consistency.

```bash
# Human-readable output
tera lint docs.yaml

# JSON output for CI/CD gates
tera lint docs.yaml --json
```

### 5. `export`

Exports the canonical definition into target client or documentation formats.

```bash
# Standalone HTML (Redoc)
tera export docs.yaml --format html -o docs.html

# Markdown documentation
tera export docs.yaml --format markdown -o API.md

# Postman collection
tera export docs.yaml --format postman -o collection.json
```

### 6. `diff`

Compares two API specifications semantically and detects breaking changes (e.g. removed endpoints, modified types, newly required parameters).

```bash
# Compare two specification files
tera diff docs.v1.yaml docs.v2.yaml

# Compare against a git revision
tera diff HEAD~1:docs.yaml docs.yaml

# JSON output for CI automation
tera diff docs.v1.yaml docs.v2.yaml --json

# CI gates: fail on breaking changes or on any drift
tera diff docs.v1.yaml docs.v2.yaml --fail-on-breaking
tera diff docs.v1.yaml docs.v2.yaml --fail-on-drift
```

### 7. `semver`

Recommends the next semantic version (`MAJOR`, `MINOR`, `PATCH`) based on the semantic diff between specifications, and optionally bumps the version in the destination specification file.

```bash
# Analyze changes and recommend bump
tera semver docs.v1.yaml docs.v2.yaml

# Compare against a git revision
tera semver HEAD~1:docs.yaml docs.yaml

# Output recommendation as JSON
tera semver docs.v1.yaml docs.v2.yaml --json

# Directly bump api.version in the target file on disk
tera semver docs.v1.yaml docs.v2.yaml --bump
```

### 8. `changelog`

Generates structured release notes following the [Keep a Changelog](https://keepachangelog.com/) standard (`Added`, `Changed`, `Removed`, `Security`) from the semantic differences between specifications.

```bash
# Print changelog markdown to stdout
tera changelog docs.v1.yaml docs.v2.yaml

# Compare against a git revision
tera changelog HEAD~1:docs.yaml docs.yaml

# Write changelog snippet to a file
tera changelog docs.v1.yaml docs.v2.yaml -o RELEASE_NOTES.md

# Prepend release section into CHANGELOG.md
tera changelog docs.v1.yaml docs.v2.yaml --append

# Output structured JSON
tera changelog docs.v1.yaml docs.v2.yaml --json
```

### 9. `sync`

Self-healing synchronization: performs a safe merge of code AST reflection with existing documentation. Technical structures (routes, methods, parameters, types, body) are updated from code, while human-written metadata (summaries, descriptions, tags, examples, error responses) are strictly preserved.

```bash
# Preview sync changes (dry-run)
tera sync main:app --doc docs.yaml

# Apply and overwrite docs.yaml with merged schema
tera sync main:app --doc docs.yaml --write

# Prune endpoints that no longer exist in code
tera sync main:app --doc docs.yaml --write --prune

# Output sync result as JSON
tera sync main:app --doc docs.yaml --json
```

### 10. `coverage`

Audits API documentation completeness across summaries, descriptions, parameter explanations, payload models, and error responses.

```bash
# View documentation coverage report
tera coverage docs.yaml

# Fail in CI if documentation coverage is below 80%
tera coverage docs.yaml --min-coverage 80

# Output coverage metrics as JSON
tera coverage docs.yaml --json
```

### 11. `security`

Audits security drift by comparing AST decorators in code (e.g. `@jwt_required`, `@login_required`) against `auth_required` contracts in the documentation.

```bash
# Audit security drift
tera security main:app --doc docs.yaml

# CI security gate: fail if any security drift is detected
tera security main:app --doc docs.yaml --fail-on-drift

# Output security drift report as JSON
tera security main:app --doc docs.yaml --json
```

### 12. `import`

Imports existing OpenAPI (3.0/3.1) or Swagger (2.0) specifications (JSON or YAML) into the canonical Tera IR (`docs.yaml`). Resolves internal `$ref` components and maps parameters, schemas, and responses.

```bash
# Import an existing OpenAPI specification into docs.yaml
tera import openapi.json -o docs.yaml

# Overwrite existing destination file
tera import swagger.yaml -o docs.yaml --force

# Inspect converted Tera IR as JSON to stdout
tera import openapi.json --json
```

### 13. `serve`

Serves interactive documentation locally with zero extra dependencies using Python's built-in HTTP server. Embeds Swagger UI or Redoc and watches `docs.yaml` for changes, reloading the specification on browser refresh.

```bash
# Serve Swagger UI locally on http://127.0.0.1:8000
tera serve docs.yaml

# Serve Redoc UI on a custom port and automatically open the browser
tera serve docs.yaml --port 8080 --ui redoc --open

# Direct endpoints available:
#   http://127.0.0.1:8000/          (Default UI)
#   http://127.0.0.1:8000/swagger   (Swagger UI)
#   http://127.0.0.1:8000/redoc     (Redoc UI)
#   http://127.0.0.1:8000/openapi.json
#   http://127.0.0.1:8000/openapi.yaml
```

---

## Configuration

`tera` can be customized via `.teraconfig.toml`:

```toml
target = "main:app"
output = "dist/openapi.json"
format = "yaml"
title = "My API"
version = "1.0.0"

[lint]
ignore = ["SEM001"]
```

Ignore patterns for scanners can be configured in `.teraignore` (using gitignore syntax).

---

## Development & Testing

```bash
pytest -v
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
