#!/usr/bin/env bash
set -e

# Colors for output
BOLD="\033[1m"
GREEN="\033[0;32m"
BLUE="\033[0;34m"
CYAN="\033[0;36m"
RESET="\033[0m"

DIST_DIR="dist"
mkdir -p "$DIST_DIR"

echo -e "${BOLD}${BLUE}=====================================================${RESET}"
echo -e "${BOLD}${BLUE}       tera-cli — Portfolio Feature Walkthrough       ${RESET}"
echo -e "${BOLD}${BLUE}=====================================================${RESET}\n"

echo -e "${BOLD}${CYAN}1. Validating Canonical Tera IR Specification against JSON Schema${RESET}"
tera validate examples/specs/docs.yaml

echo -e "\n${BOLD}${CYAN}2. Static Linting (Rule Enforcement)${RESET}"
tera lint examples/specs/docs.yaml

echo -e "\n${BOLD}${CYAN}3. Semantic & Structural Inconsistency Audit (Deterministic, No-LLM)${RESET}"
tera audit examples/specs/docs.yaml

echo -e "\n${BOLD}${CYAN}4. AST & Reflection Code Scanning (Flask App)${RESET}"
tera scan examples/flask_app/app.py:app -o "$DIST_DIR/scanned_flask.yaml"

echo -e "\n${BOLD}${CYAN}5. Native Introspection Code Scanning (FastAPI App)${RESET}"
tera scan examples/fastapi_app/app.py:app -o "$DIST_DIR/scanned_fastapi.yaml"

echo -e "\n${BOLD}${CYAN}6. Reverse Engineering from HTTP Archive (HAR Traffic)${RESET}"
tera import examples/specs/traffic.har -o "$DIST_DIR/imported_har.yaml"

echo -e "\n${BOLD}${CYAN}7. Multi-version Postman Collection Import${RESET}"
tera import examples/specs/postman_collection.json -o "$DIST_DIR/imported_postman.yaml"

echo -e "\n${BOLD}${CYAN}8. Building Standard OpenAPI 3.0 Specification${RESET}"
tera build examples/specs/docs.yaml -o "$DIST_DIR/openapi.json"

echo -e "\n${BOLD}${CYAN}9. Exporting Human-Readable Documentation (Markdown)${RESET}"
tera export examples/specs/docs.yaml --format markdown -o "$DIST_DIR/API.md"

echo -e "\n${BOLD}${CYAN}10. Exporting Standalone Interactive HTML (Redoc)${RESET}"
tera export examples/specs/docs.yaml --format html -o "$DIST_DIR/docs.html"

echo -e "\n${BOLD}${CYAN}11. Semantic Diff & Breaking Change Detection (v1 -> v2)${RESET}"
tera diff examples/specs/docs.yaml examples/specs/docs.v2.yaml || true

echo -e "\n${BOLD}${CYAN}12. Automatic SemVer Bump Recommendation${RESET}"
tera semver examples/specs/docs.yaml examples/specs/docs.v2.yaml

echo -e "\n${BOLD}${CYAN}13. Automated Keep a Changelog Release Notes Generator${RESET}"
tera changelog examples/specs/docs.yaml examples/specs/docs.v2.yaml -o "$DIST_DIR/CHANGELOG_SNIPPET.md"

echo -e "\n${BOLD}${CYAN}14. Documentation Completeness Coverage Audit${RESET}"
tera coverage examples/specs/docs.yaml

echo -e "\n${BOLD}${CYAN}15. Security Drift Detection (Code AST vs Doc Contracts)${RESET}"
tera security examples/flask_app/app.py:app --doc examples/specs/docs.yaml

echo -e "\n${BOLD}${CYAN}16. Architectural Dependency Graph Generation (Mermaid)${RESET}"
tera graph examples/specs/docs.yaml -o "$DIST_DIR/architecture.mmd"

echo -e "\n${BOLD}${GREEN}=====================================================${RESET}"
echo -e "${BOLD}${GREEN}   Demo complete! All generated artifacts saved in:   ${RESET}"
echo -e "${BOLD}${GREEN}                     ${DIST_DIR}/                     ${RESET}"
echo -e "${BOLD}${GREEN}=====================================================${RESET}"

