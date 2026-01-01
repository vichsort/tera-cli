from pathlib import Path
from typing import List, Dict, Optional
from pydantic import ValidationError
from tera.core import TeraConfig
from tera.domain import TeraSchema
from tera.domain.linting import LintIssue, LintSeverity
from tera.adapters import FileLoader
from tera.services.rules import ALL_RULES

class LinterService:
    """
    Reads and validates Tera documentation files (YAML/JSON). 
    """
    def __init__(self, config: Optional[TeraConfig] = None):
        self.ignore_list = config.lint.ignore if config else []

    def lint(self, file_path: Path) -> List[LintIssue]:
        raw_data, issues = FileLoader.load(file_path)
        if raw_data is None:
            return issues

        schema_issues = self._validate_structure(raw_data)
        issues.extend(schema_issues)
        
        if any(i.severity == LintSeverity.ERROR for i in issues):
            return issues

        try:
            schema = TeraSchema(**raw_data)
            for rule_function in ALL_RULES:
                issues.extend(rule_function(schema))
        except Exception as e:
             issues.append(LintIssue(
                code="rule_engine_error", 
                message=str(e), 
                severity=LintSeverity.ERROR
            ))

        return self._filter_ignored(issues)
    
    def _filter_ignored(self, issues: List[LintIssue]) -> List[LintIssue]:
        """Remove warinings that the user asked to ignore."""
        filtered = []
        for issue in issues:
            if issue.severity == LintSeverity.ERROR:
                filtered.append(issue)
            elif issue.code not in self.ignore_list:
                filtered.append(issue)
        
        return filtered

    def _validate_structure(self, data: Dict) -> List[LintIssue]:
        issues = []
        try:
            TeraSchema(**data)
        except ValidationError as e:
            for err in e.errors():
                loc = " -> ".join(str(x) for x in err['loc'])
                issues.append(LintIssue(
                    code="schema_error",
                    message=err['msg'],
                    severity=LintSeverity.ERROR,
                    location=loc
                ))
        return issues