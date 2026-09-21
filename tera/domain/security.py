from typing import Literal, List
from pydantic import BaseModel, ConfigDict, Field

DriftType = Literal['missing_auth_in_code', 'missing_auth_in_doc', 'undocumented_endpoint']
SecuritySeverity = Literal['CRITICAL', 'WARNING']

class SecurityIssue(BaseModel):
    """
    Represents a discrepancy between security decorators in code and documentation auth contracts.
    """
    model_config = ConfigDict(extra='forbid')

    method: str
    path: str
    drift_type: DriftType
    severity: SecuritySeverity
    description: str

class SecurityDriftReport(BaseModel):
    """
    Consolidated security drift report cross-referencing code AST reflection with documentation IR.
    """
    model_config = ConfigDict(extra='forbid')

    total_code_endpoints: int
    total_doc_endpoints: int
    has_drift: bool
    critical_count: int
    warning_count: int
    issues: List[SecurityIssue] = Field(default_factory=list[SecurityIssue])
