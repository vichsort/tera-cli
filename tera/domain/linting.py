from enum import Enum
from typing import Optional
from pydantic import BaseModel

class LintSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"

class LintIssue(BaseModel):
    """
    Represents a single problem in an analysis.
    """
    code: str
    message: str
    severity: LintSeverity
    location: Optional[str] = None
    line: Optional[int] = None

    def __str__(self):
        prefix = f"[{self.severity.value.upper()}]"
        loc = f" at {self.location}" if self.location else ""
        line = f" (Line {self.line})" if self.line else ""
        return f"{prefix} {self.message}{loc}{line}"