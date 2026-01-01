from typing import List
from tera.domain import TeraSchema
from tera.domain.linting import LintIssue, LintSeverity

def check_general_info(schema: TeraSchema) -> List[LintIssue]:
    issues = []
    if not schema.api.description:
        issues.append(LintIssue(
            code="missing_api_description",
            message="API definition is missing a general description.",
            severity=LintSeverity.WARNING,
            location="api"
        ))
    return issues

def check_endpoints(schema: TeraSchema) -> List[LintIssue]:
    issues = []
    write_methods = ['POST', 'PUT', 'DELETE', 'PATCH']
    
    for ep in schema.endpoints:
        ep_loc = f"{ep.method} {ep.path}"
        
        # RULE - description or summary
        if not ep.description and not ep.summary:
            issues.append(LintIssue(
                code="missing_description",
                message="Endpoint lacks summary or description.",
                severity=LintSeverity.WARNING,
                location=ep_loc
            ))

        # RULE - auth in unsafe methods as delete or put
        if ep.method in write_methods and not ep.auth_required:
            issues.append(LintIssue(
                code="unsafe_operation",
                message=f"Public {ep.method} endpoint detected.",
                severity=LintSeverity.WARNING,
                location=ep_loc
            ))
            
        # RULE -  responses
        if not ep.responses.success:
            issues.append(LintIssue(
                code="missing_response",
                message="No success response defined.",
                severity=LintSeverity.WARNING,
                location=ep_loc
            ))

    return issues

ALL_RULES = [check_general_info, check_endpoints]