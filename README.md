# tera-cli

[![CI](https://github.com/vichsort/tera-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/vichsort/tera-cli/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Type Checking](https://img.shields.io/badge/type--checking-pyright%20strict-blueviolet)](https://github.com/microsoft/pyright)
[![Code Style](https://img.shields.io/badge/architecture-clean%20%26%20solid-informational)](https://blog.cleancoder.com/)

> **Documentation as Code Tool** — Canonical Intermediate Representation (IR) Hub for API Specifications.

`tera-cli` is a developer-centric CLI designed to decouple API documentation inputs from outputs. Instead of translating directly from code to documentation, `tera` uses a canonical intermediate representation (`docs.yaml`) that can be scanned from source code, written by hand with full IDE autocomplete, reverse-engineered from network traffic, linted in CI gates, and exported into multiple formats.

```text
Flask App (scan) ────────┐
FastAPI App (scan) ──────┤
OpenAPI spec (import) ───┤
Postman Collection (imp) ┼─→ docs.yaml (Canonical IR) ─┬─→ OpenAPI 3.0 (build)
HTTP Archive / HAR (imp) ┤                             ├─→ Markdown Documentation (export)
HTTP/HTTPS URL (import) ─┤                             ├─→ Interactive HTML / Redoc (export)
Git Revision (driver) ───┤                             ├─→ Postman Collection v2.1 (export)
Handcrafted YAML (init) ─┘                             └─→ Local Dev Server (serve)
```

---

## Architecture

Built with Clean Architecture principles and strict layer isolation:

- **`domain`**: Pydantic models defining the canonical schema (`TeraSchema`, `Endpoint`, `ParamField`, `BodyField`) and domain reporting models (`ValidationReport`, `AuditReport`, `SecurityDriftReport`, `CoverageReport`, `SchemaDiff`, `SemverResult`, `SyncResult`). Strictly agnostic of I/O, presentation, and external frameworks.
- **`contracts`**: Python `Protocol` interfaces (`TeraDriver`, `TeraWriter`, `TeraLinter`) enforcing strict input/output contracts.
- **`core`**: Central registry and configuration:
  - `DriverRegistry` & `WriterRegistry`: Dynamic resolution of drivers and writers.
  - `PluginManager`: Extensibility through `importlib.metadata` entry points (`tera.plugins`) and local `tera.toml` declarations.
  - `TeraConfig`: Project configuration loaded from `.teraconfig.toml` and `.teraignore`.
- **`drivers`** (Tier 1 Built-in Ingestion):
  - `YamlFileDriver`: Ingests canonical `docs.yaml` and `.json` specifications.
  - `FlaskAppDriver`: AST static analysis and introspection of Flask routes, converters (`<int:id>`, `<float:val>`), docstrings, security decorators (`@jwt_required`, `@login_required`), and Pydantic request models.
  - `FastApiDriver`: Zero-dependency introspection of FastAPI applications via duck-typed `app.openapi()`.
  - `OpenApiDriver`: Ingests OpenAPI 3.0/3.1 and Swagger 2.0 specifications with internal `$ref` resolution.
  - `PostmanCollectionDriver`: Multi-version normalizer supporting Postman Collection v1.0, v2.0, v2.1, and v3 schemas.
  - `HarDriver`: Reverse engineering of HTTP Archive (`.har`) traffic with heuristic dynamic route collapsing (`/users/{id}`) and payload inference.
  - `HttpDriver`: Ingestion of remote specifications over HTTP/HTTPS with custom authentication headers.
  - `GitFileDriver`: Direct loading of specifications across Git revisions (`git:HEAD~1:docs.yaml`, `HEAD:spec.json`).
- **`adapters`**: Schema transformations (e.g. `TeraOpenApiAdapter` converting canonical schemas into OpenAPI 3.0.3 structures).
- **`writers`** (Output Renderers):
  - `OpenApiJsonWriter`, `OpenApiYamlWriter`: Standard OpenAPI 3.0 specifications.
  - `MarkdownWriter`: Human-readable Markdown API documentation.
  - `HtmlWriter`: Standalone offline Redoc HTML documentation.
  - `PostmanWriter`: Postman Collection v2.1.
  - `JsonFileWriter`, `YamlFileWriter`: Canonical Tera IR output formats.
- **`services`**: Core business logic and orchestration pipelines (`run_pipeline`, `LinterService`, `DiffService`, `SemverService`, `ChangelogService`, `SyncService`, `CoverageService`, `SecurityDriftService`, `AuditService`, `GraphService`, `DocServer`, `ValidationService`, `SchemaService`).
- **`cli`**: Subcommands powered by Typer and decoupled presenters (`tera/cli/presenters.py`).

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

Verify the installation:

```bash
tera --help
```

---

## Commands

### 1. `init`

Scaffolds a new documentation project with sample definitions, configuration, and editor schema directives.

```bash
# Standard boilerplate
tera init

# Complete example with auth, parameters, payloads, and error responses
tera init --complete

# Skip generating .teraconfig.toml
tera init --no-config
```

The generated `docs.yaml` includes the `# yaml-language-server: $schema=...` directive, providing real-time autocompletion and validation in VS Code, Neovim, and JetBrains IDEs.

### 2. `schema`

Exports the official JSON Schema for the canonical Tera Intermediate Representation (`TeraSchema`).

```bash
# Print JSON Schema to stdout
tera schema

# Export to a file
tera schema -o schemas/tera-schema.json
```

### 3. `validate`

Validates a `docs.yaml` specification directly against the canonical Tera IR schema, enforcing type rules, required fields, and forbidding unknown properties without executing build or lint pipelines.

```bash
# Validate default docs.yaml
tera validate

# Validate specific file
tera validate path/to/spec.yaml

# Output structured JSON for CI/CD gates
tera validate docs.yaml --json
```

### 4. `scan`

Extracts API schemas directly from application source code using AST reflection and introspection without starting a live server.

```bash
# Scan Flask application
tera scan my_app:app -o docs.yaml

# Scan using direct file path
tera scan src/app.py:app -o docs.yaml

# Scan FastAPI application
tera scan inventory_service:app -o docs.yaml
```

### 5. `build`

Compiles canonical `docs.yaml` into standard OpenAPI 3.0 specification.

```bash
# Compile to JSON
tera build docs.yaml -o openapi.json

# Compile to YAML
tera build docs.yaml -o openapi.yaml
```

### 6. `lint`

Performs static analysis on documentation definitions to enforce schema validity and semantic documentation quality rules.

```bash
# Human-readable output
tera lint docs.yaml

# JSON output for CI/CD automation
tera lint docs.yaml --json
```

### 7. `export`

Exports the canonical definition into target client or documentation formats.

```bash
# Standalone HTML (Redoc)
tera export docs.yaml --format html -o docs.html

# Markdown documentation
tera export docs.yaml --format markdown -o API.md

# Postman collection v2.1
tera export docs.yaml --format postman -o collection.json
```

### 8. `diff`

Compares two API specifications semantically and detects breaking changes (e.g. removed endpoints, modified types, newly required parameters, base URL shifts).

```bash
# Compare two specification files
tera diff docs.v1.yaml docs.v2.yaml

# Compare working directory against a git revision
tera diff HEAD~1:docs.yaml docs.yaml

# Output structured diff JSON
tera diff docs.v1.yaml docs.v2.yaml --json

# CI gates: fail on breaking changes or on any drift
tera diff docs.v1.yaml docs.v2.yaml --fail-on-breaking
tera diff docs.v1.yaml docs.v2.yaml --fail-on-drift
```

### 9. `semver`

Recommends the next semantic version (`MAJOR`, `MINOR`, `PATCH`) based on semantic contract diffs and optionally bumps the version on disk.

```bash
# Analyze changes and recommend bump
tera semver docs.v1.yaml docs.v2.yaml

# Compare against a git revision
tera semver HEAD~1:docs.yaml docs.yaml

# Output recommendation as JSON
tera semver docs.v1.yaml docs.v2.yaml --json

# Automatically bump api.version in the target file on disk
tera semver docs.v1.yaml docs.v2.yaml --bump
```

### 10. `changelog`

Generates structured release notes following the [Keep a Changelog](https://keepachangelog.com/) standard (`Added`, `Changed`, `Removed`, `Security`) from semantic differences.

```bash
# Print changelog to stdout
tera changelog docs.v1.yaml docs.v2.yaml

# Write changelog snippet to a file
tera changelog docs.v1.yaml docs.v2.yaml -o RELEASE_NOTES.md

# Prepend release section into an existing CHANGELOG.md
tera changelog docs.v1.yaml docs.v2.yaml --append
```

### 11. `sync`

Self-healing synchronization: performs a safe merge of code AST reflection with existing documentation. Technical structures (routes, methods, parameters, types, body) are updated from code, while human-written metadata (summaries, descriptions, tags, examples, error responses) are strictly preserved.

```bash
# Preview sync changes (dry-run)
tera sync main:app --doc docs.yaml

# Apply and overwrite docs.yaml with merged schema
tera sync main:app --doc docs.yaml --write

# Prune endpoints that no longer exist in code
tera sync main:app --doc docs.yaml --write --prune
```

### 12. `coverage`

Audits API documentation completeness across summaries, descriptions, parameter explanations, payload models, and error responses.

```bash
# View documentation coverage report
tera coverage docs.yaml

# Fail in CI if documentation coverage is below threshold
tera coverage docs.yaml --min-coverage 80

# Output coverage metrics as JSON
tera coverage docs.yaml --json
```

### 13. `security`

Audits security drift by comparing AST decorators in code (e.g. `@jwt_required`, `@login_required`) against `auth_required` contracts in the documentation.

```bash
# Audit security drift
tera security main:app --doc docs.yaml

# CI security gate: fail if any security drift is detected
tera security main:app --doc docs.yaml --fail-on-drift
```

### 14. `import`

Imports external specifications or captures into canonical Tera IR (`docs.yaml`).

```bash
# Import OpenAPI / Swagger (JSON or YAML)
tera import openapi.json -o docs.yaml

# Import from remote URL
tera import https://api.example.com/openapi.json -o docs.yaml

# Reverse-engineer API specification from HTTP Archive (.har)
tera import traffic.har -o docs.yaml

# Import Postman Collection (v1.0, v2.0, v2.1, v3)
tera import collection.json -o docs.yaml
```

### 15. `serve`

Serves interactive documentation locally with zero extra dependencies using Python's built-in HTTP server. Embeds Swagger UI and Redoc with automatic specification reloading on browser refresh.

```bash
# Serve Swagger UI locally on http://127.0.0.1:8000
tera serve docs.yaml

# Serve Redoc on a custom port and automatically open the browser
tera serve docs.yaml --port 8080 --ui redoc --open
```

### 16. `graph`

Generates architectural relationship and dependency diagrams across API endpoints in Mermaid syntax (`flowchart TD / LR`), grouping resources by tags and identifying creation/lifecycle dependencies (`creates {id}`) and sub-resources.

```bash
# Output Mermaid diagram to stdout
tera graph docs.yaml

# Save diagram to file
tera graph docs.yaml -o architecture.mmd

# Change layout direction
tera graph docs.yaml --direction LR
```

### 17. `audit`

Performs deterministic semantic and structural inconsistency audits without external LLMs. Identifies semantic mismatches across HTTP methods, status codes, path pluralities, and unprotected destructive operations.

```bash
# Run consistency audit
tera audit docs.yaml

# Fail in CI on any critical or warning inconsistency
tera audit docs.yaml --strict

# Enforce a minimum semantic coherence score (0-100)
tera audit docs.yaml --min-score 90
```

---

## CI/CD Integration

### Pre-commit Hooks

Add `tera` to your `.pre-commit-config.yaml` to enforce valid specifications and prevent semantic issues before committing:

```yaml
repos:
  - repo: https://github.com/vichsort/tera-cli
    rev: v0.1.0
    hooks:
      - id: tera-lint
      - id: tera-audit
```

### GitHub Actions

Use the official composite GitHub Action to enforce documentation gates in your CI workflows:

```yaml
name: API Documentation Gate

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Validate Tera Specification
        uses: vichsort/tera-cli@master
        with:
          command: validate
          file: docs.yaml

      - name: Audit Consistency
        uses: vichsort/tera-cli@master
        with:
          command: audit
          file: docs.yaml
          args: --strict

      - name: Detect Breaking Changes
        uses: vichsort/tera-cli@master
        with:
          command: diff
          args: HEAD~1:docs.yaml docs.yaml --fail-on-breaking
```

---

## Configuration

`tera` can be customized via `.teraconfig.toml`:

```toml
# Default import string for 'tera scan'
target = "main:app"

# Default output path
output = "dist/openapi.json"

# Output format preference
format = "yaml"

title = "My Project API"
version = "1.0.0"

[lint]
ignore = ["SEM001", "missing_description"]
```

Ignore patterns for scanners can be configured in `.teraignore` (using gitignore syntax).

---

## Extensibility & Plugins

`tera-cli` employs a 3-tier extensibility model:

1. **Tier 1 (Built-in Zero-Install)**: OpenAPI, YAML/JSON, Git, HTTP/HTTPS, Postman, HAR, Flask, FastAPI.
2. **Tier 2 (Lazy Extras)**: Installed on-demand via optional dependencies.
3. **Tier 3 (External & Local Plugins)**:
   - Dynamic discovery via `importlib.metadata` entry points group `tera.plugins`.
   - Local plugin modules configured in `tera.toml` pointing to callable registration hooks:

```toml
[plugins]
load = ["custom_plugin:register_tera_plugin"]
```

The registration function receives `(driver_registry, writer_registry)` and registers custom drivers or writers:

```python
from tera.core.registry import DriverRegistry, WriterRegistry

def register_tera_plugin(driver_registry: DriverRegistry, writer_registry: WriterRegistry) -> None:
    driver_registry.register(
        "custom",
        lambda source: CustomDriver(source),
        matcher=lambda s: str(s).endswith(".custom"),
        priority=85,
    )
```

A complete end-to-end working example is available in [`examples/plugin_example/`](examples/plugin_example/).

---

## Examples & Demo Walkthrough

The repository includes a complete suite of examples under `examples/`:
- `examples/flask_app/`: Sample Flask app with auth decorators and Pydantic models.
- `examples/fastapi_app/`: Duck-typed FastAPI app showcasing native introspection.
- `examples/specs/`: Canonical `docs.yaml`, evolved `docs.v2.yaml`, HTTP Archive `traffic.har`, and Postman Collection.
- `examples/plugin_example/`: End-to-end custom plugin with `.routes` toy driver.

To run an end-to-end automated walkthrough of all features:

```bash
make demo
```

Run tests and type checking:

```bash
make test        # Runs pytest (226+ tests)
make typecheck   # Runs pyright strict mode
make check       # Runs test, typecheck, lint, and validate
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
