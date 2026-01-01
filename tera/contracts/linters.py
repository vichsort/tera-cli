from typing import Protocol, List
from pathlib import Path
from tera.domain.linting import LintIssue

class TeraLinter(Protocol):
    """
    Contract for documentation validators.
    Responsible for analyzing a file and returning a list of issues (Errors or Warnings).
    """
    def lint(self, file_path: Path) -> List[LintIssue]:
        """
        Analyzes a file and returns a list of found issues.
        Should not raise exceptions for validation errors, but return them as LintIssues.
        """
        ...