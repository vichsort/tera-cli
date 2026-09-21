from typing import Optional, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, computed_field
from tera.domain.models import HTTPMethod

ChangeKind = Literal['added', 'removed', 'modified']
ChangeCategory = Literal['structural', 'metadata']
ImpactLevel = Literal['breaking', 'non_breaking']

class DiffEntry(BaseModel):
    """
    Represents an atomic difference between two schema elements.
    """
    model_config = ConfigDict(extra='forbid')

    path: str
    kind: ChangeKind
    category: ChangeCategory
    impact: ImpactLevel
    description: str
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None

class EndpointDiff(BaseModel):
    """
    Represents all differences associated with a specific endpoint (method + path).
    """
    model_config = ConfigDict(extra='forbid')

    method: HTTPMethod
    path: str
    kind: ChangeKind
    impact: ImpactLevel
    changes: list[DiffEntry] = Field(default_factory=list[DiffEntry])

class SchemaDiff(BaseModel):
    """
    Root model representing the semantic difference between two TeraSchema specifications.
    """
    model_config = ConfigDict(extra='forbid')

    api_changes: list[DiffEntry] = Field(default_factory=list[DiffEntry])
    endpoint_diffs: list[EndpointDiff] = Field(default_factory=list[EndpointDiff])

    @computed_field
    @property
    def has_breaking_changes(self) -> bool:
        if any(change.impact == 'breaking' for change in self.api_changes):
            return True
        for ep in self.endpoint_diffs:
            if ep.impact == 'breaking':
                return True
            if any(c.impact == 'breaking' for c in ep.changes):
                return True
        return False

    @computed_field
    @property
    def is_empty(self) -> bool:
        return len(self.api_changes) == 0 and len(self.endpoint_diffs) == 0

    @computed_field
    @property
    def total_changes(self) -> int:
        ep_count = 0
        for ep in self.endpoint_diffs:
            if ep.kind == 'modified':
                ep_count += len(ep.changes)
            else:
                ep_count += 1
        return len(self.api_changes) + ep_count

    @computed_field
    @property
    def breaking_count(self) -> int:
        count = sum(1 for c in self.api_changes if c.impact == 'breaking')
        for ep in self.endpoint_diffs:
            if ep.kind == 'modified':
                count += sum(1 for c in ep.changes if c.impact == 'breaking')
            elif ep.impact == 'breaking':
                count += 1
        return count
