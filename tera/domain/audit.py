from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

AuditSeverity = Literal["CRITICAL", "WARNING", "INFO"]


class AuditIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: AuditSeverity
    method: str
    path: str
    message: str
    suggestion: Optional[str] = None


class AuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_endpoints: int
    total_issues: int
    critical_count: int
    warning_count: int
    info_count: int
    coherence_score: float
    issues: List[AuditIssue] = Field(default_factory=list[AuditIssue])

    @property
    def has_critical(self) -> bool:
        return self.critical_count > 0

    @property
    def has_issues(self) -> bool:
        return self.total_issues > 0
