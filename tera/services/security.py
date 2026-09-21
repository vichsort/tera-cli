from typing import List
from tera.domain import (
    TeraSchema,
    SecurityIssue,
    SecurityDriftReport
)

class SecurityDriftService:
    """
    Audits security drift by cross-referencing code AST security decorators against documentation contracts.
    """

    def audit(self, code_schema: TeraSchema, doc_schema: TeraSchema) -> SecurityDriftReport:
        code_map = code_schema.endpoint_map
        doc_map = doc_schema.endpoint_map

        issues: List[SecurityIssue] = []

        # Compare endpoints present in both
        common_keys = sorted(set(code_map.keys()) & set(doc_map.keys()), key=lambda k: (k[1], k[0]))
        for key in common_keys:
            code_ep = code_map[key]
            doc_ep = doc_map[key]

            # Case 1: Doc claims auth is required, but code has no auth decorator
            if doc_ep.auth_required and not code_ep.auth_required:
                issues.append(SecurityIssue(
                    method=code_ep.method,
                    path=code_ep.path,
                    drift_type="missing_auth_in_code",
                    severity="CRITICAL",
                    description=(
                        f"Endpoint '{code_ep.identifier}' is documented as requiring authentication "
                        "(auth_required: true), but has no auth decorators in code."
                    )
                ))

            # Case 2: Code enforces auth, but doc claims public access
            elif code_ep.auth_required and not doc_ep.auth_required:
                issues.append(SecurityIssue(
                    method=code_ep.method,
                    path=code_ep.path,
                    drift_type="missing_auth_in_doc",
                    severity="CRITICAL",
                    description=(
                        f"Endpoint '{code_ep.identifier}' requires authentication in code via decorators, "
                        "but is documented as public (auth_required: false)."
                    )
                ))

        # Check endpoints in code that are missing in docs
        code_only_keys = sorted(set(code_map.keys()) - set(doc_map.keys()), key=lambda k: (k[1], k[0]))
        for key in code_only_keys:
            code_ep = code_map[key]
            if code_ep.auth_required:
                issues.append(SecurityIssue(
                    method=code_ep.method,
                    path=code_ep.path,
                    drift_type="undocumented_endpoint",
                    severity="WARNING",
                    description=(
                        f"Authenticated endpoint '{code_ep.identifier}' exists in code with auth decorators, "
                        "but is completely missing from documentation."
                    )
                ))

        critical_count = sum(1 for i in issues if i.severity == "CRITICAL")
        warning_count = sum(1 for i in issues if i.severity == "WARNING")

        return SecurityDriftReport(
            total_code_endpoints=len(code_schema.endpoints),
            total_doc_endpoints=len(doc_schema.endpoints),
            has_drift=len(issues) > 0,
            critical_count=critical_count,
            warning_count=warning_count,
            issues=issues
        )

