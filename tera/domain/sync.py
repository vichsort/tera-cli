from typing import List
from pydantic import BaseModel, ConfigDict, Field
from tera.domain.models import TeraSchema

class SyncResult(BaseModel):
    """
    Result of synchronizing code AST reflection with an existing documentation schema.
    """
    model_config = ConfigDict(extra='forbid')

    merged_schema: TeraSchema
    endpoints_added: List[str] = Field(default_factory=list[str])
    endpoints_updated: List[str] = Field(default_factory=list[str])
    endpoints_orphaned: List[str] = Field(default_factory=list[str])
    endpoints_pruned: List[str] = Field(default_factory=list[str])
    annotations_preserved: int = 0

