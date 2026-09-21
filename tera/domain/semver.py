from typing import Literal, List
from pydantic import BaseModel, ConfigDict, Field

SemverBump = Literal['major', 'minor', 'patch', 'none']

class SemverResult(BaseModel):
    """
    Result of a semantic version calculation based on specification diff.
    """
    model_config = ConfigDict(extra='forbid')

    current_version: str
    bump: SemverBump
    next_version: str
    reasons: List[str] = Field(default_factory=list[str])
    breaking_count: int = 0
