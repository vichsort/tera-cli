from typing import List, Set
import re

from tera.domain.models import TeraSchema, Endpoint
from tera.domain.audit import AuditIssue, AuditReport

MUTATION_VERBS: Set[str] = {
    "create", "add", "new", "insert", "delete", "remove", "destroy", "drop",
    "update", "modify", "edit", "patch", "save",
    "criar", "adicionar", "inserir", "deletar", "remover", "excluir",
    "atualizar", "alterar", "modificar", "salvar",
}

RETRIEVAL_VERBS: Set[str] = {
    "get", "list", "fetch", "retrieve", "read", "search", "find",
    "buscar", "listar", "obter", "consultar", "pegar", "carregar", "achar",
}

PUBLIC_POST_ALLOWLIST: Set[str] = {
    "login", "signin", "auth", "token", "register", "signup",
    "forgot", "reset", "webhook", "callback", "ping", "health",
}


class AuditService:
    """
    Deterministic inconsistency and quality audit engine without external LLMs.
    Verifies semantic coherence across HTTP verbs, status codes, paths, and security.
    """

    def audit(self, schema: TeraSchema) -> AuditReport:
        issues: List[AuditIssue] = []

        for ep in schema.endpoints:
            issues.extend(self._check_verb_coherence(ep))
            issues.extend(self._check_status_code_coherence(ep))
            issues.extend(self._check_path_plurality_coherence(ep))
            issues.extend(self._check_security_coherence(ep))

        critical_count = sum(1 for i in issues if i.severity == "CRITICAL")
        warning_count = sum(1 for i in issues if i.severity == "WARNING")
        info_count = sum(1 for i in issues if i.severity == "INFO")

        # Score computation: start at 100, deduct penalties based on severity
        total_endpoints = len(schema.endpoints)
        penalty = (critical_count * 20.0) + (warning_count * 5.0) + (info_count * 1.0)
        coherence_score = max(0.0, 100.0 - penalty) if total_endpoints > 0 else 100.0

        return AuditReport(
            total_endpoints=total_endpoints,
            total_issues=len(issues),
            critical_count=critical_count,
            warning_count=warning_count,
            info_count=info_count,
            coherence_score=round(coherence_score, 1),
            issues=issues,
        )

    def _check_verb_coherence(self, ep: Endpoint) -> List[AuditIssue]:
        issues: List[AuditIssue] = []
        words = self._extract_words(ep.summary)
        first_word = words[0].lower() if words else ""

        if ep.method == "GET" and first_word in MUTATION_VERBS:
            issues.append(
                AuditIssue(
                    code="INC001",
                    severity="WARNING",
                    method=ep.method,
                    path=ep.path,
                    message=f"GET endpoint has mutation verb '{first_word}' in summary.",
                    suggestion="Use POST, PUT, PATCH, or DELETE for mutations, or rename summary to describe retrieval.",
                )
            )
        elif ep.method == "DELETE" and first_word in RETRIEVAL_VERBS:
            issues.append(
                AuditIssue(
                    code="INC001",
                    severity="WARNING",
                    method=ep.method,
                    path=ep.path,
                    message=f"DELETE endpoint has retrieval verb '{first_word}' in summary.",
                    suggestion="Rename summary to describe resource removal (e.g. 'Delete item').",
                )
            )
        elif ep.method == "POST" and first_word in {"delete", "remove", "deletar", "remover", "excluir"}:
            issues.append(
                AuditIssue(
                    code="INC001",
                    severity="WARNING",
                    method=ep.method,
                    path=ep.path,
                    message=f"POST endpoint appears to perform deletion based on summary ('{first_word}').",
                    suggestion="Consider using the standard DELETE HTTP method instead.",
                )
            )

        return issues

    def _check_status_code_coherence(self, ep: Endpoint) -> List[AuditIssue]:
        issues: List[AuditIssue] = []
        success = ep.responses.success

        # 204 No Content with response body
        if success.status == 204 and success.example is not None:
            issues.append(
                AuditIssue(
                    code="INC002",
                    severity="CRITICAL",
                    method=ep.method,
                    path=ep.path,
                    message="HTTP 204 (No Content) must not return a response payload.",
                    suggestion="Remove the success example or change status code to 200 OK.",
                )
            )

        # 201 Created on GET or DELETE
        if success.status == 201 and ep.method in ("GET", "DELETE"):
            issues.append(
                AuditIssue(
                    code="INC002",
                    severity="WARNING",
                    method=ep.method,
                    path=ep.path,
                    message=f"HTTP 201 (Created) is unexpected for {ep.method} requests.",
                    suggestion=f"Use status 200 OK or 204 No Content for {ep.method}.",
                )
            )

        # 200 OK when summary says 'Create'
        words = self._extract_words(ep.summary)
        first_word = words[0].lower() if words else ""
        if ep.method == "POST" and success.status == 200 and first_word in {"create", "criar", "insert", "inserir"}:
            issues.append(
                AuditIssue(
                    code="INC002",
                    severity="INFO",
                    method=ep.method,
                    path=ep.path,
                    message="POST endpoint creating a resource returns 200 OK instead of standard 201 Created.",
                    suggestion="Consider returning HTTP 201 Created when creating new resources.",
                )
            )

        return issues

    def _check_path_plurality_coherence(self, ep: Endpoint) -> List[AuditIssue]:
        issues: List[AuditIssue] = []
        if ep.method != "GET":
            return issues

        clean_path = ep.path.rstrip("/")
        last_segment = clean_path.split("/")[-1] if "/" in clean_path else clean_path
        success_example = ep.responses.success.example

        # Single item path (e.g. /users/{id}) returning a list
        if last_segment.startswith("{") and last_segment.endswith("}"):
            if isinstance(success_example, list):
                issues.append(
                    AuditIssue(
                        code="INC003",
                        severity="WARNING",
                        method=ep.method,
                        path=ep.path,
                        message=f"Single-item endpoint '{ep.path}' returns an array instead of an object.",
                        suggestion="Ensure item endpoints return the specific object representation.",
                    )
                )

        # Collection path (e.g. /users) returning a plain object without pagination keys
        elif last_segment.endswith("s") and len(last_segment) > 2 and not last_segment.startswith("{"):
            if isinstance(success_example, dict):
                pagination_keys = {"items", "results", "data", "records", "rows"}
                has_collection_key = any(k in success_example for k in pagination_keys)
                if not has_collection_key:
                    issues.append(
                        AuditIssue(
                            code="INC003",
                            severity="WARNING",
                            method=ep.method,
                            path=ep.path,
                            message=f"Collection endpoint '{ep.path}' returns a single object without collection keys (items/results/data).",
                            suggestion="Return an array of items or a paginated object containing 'items'.",
                        )
                    )

        return issues

    def _check_security_coherence(self, ep: Endpoint) -> List[AuditIssue]:
        issues: List[AuditIssue] = []

        if not ep.auth_required:
            if ep.method in ("DELETE", "PUT", "PATCH"):
                issues.append(
                    AuditIssue(
                        code="INC004",
                        severity="CRITICAL",
                        method=ep.method,
                        path=ep.path,
                        message=f"Destructive/mutating endpoint '{ep.method} {ep.path}' is publicly accessible without authentication.",
                        suggestion="Set auth_required: true or protect the route with an authentication decorator.",
                    )
                )
            elif ep.method == "POST":
                # Check if path segment matches an allowed public pattern
                path_lower = ep.path.lower()
                is_public_allowed = any(keyword in path_lower for keyword in PUBLIC_POST_ALLOWLIST)
                if not is_public_allowed:
                    issues.append(
                        AuditIssue(
                            code="INC004",
                            severity="WARNING",
                            method=ep.method,
                            path=ep.path,
                            message=f"POST endpoint '{ep.path}' is publicly accessible without authentication.",
                            suggestion="Verify if this endpoint genuinely allows unauthenticated submissions.",
                        )
                    )

        return issues

    @staticmethod
    def _extract_words(text: str) -> List[str]:
        clean = re.sub(r"[^a-zA-Z0-9_\-\s]", " ", text)
        return clean.strip().split()
