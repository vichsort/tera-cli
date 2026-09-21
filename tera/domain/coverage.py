from typing import List, Dict
from pydantic import BaseModel, ConfigDict, Field

class EndpointCoverage(BaseModel):
    """
    Coverage evaluation metrics for a single API endpoint.
    """
    model_config = ConfigDict(extra='forbid')

    method: str
    path: str
    has_summary: bool
    has_description: bool
    has_error_responses: bool
    total_params: int
    documented_params: int
    total_body_fields: int
    documented_body_fields: int
    score: float
    missing_items: List[str] = Field(default_factory=list[str])

class CoverageReport(BaseModel):
    """
    Consolidated documentation coverage report across the entire API schema.
    """
    model_config = ConfigDict(extra='forbid')

    total_endpoints: int
    overall_score: float
    summaries_score: float
    descriptions_score: float
    params_score: float
    body_score: float
    errors_score: float
    endpoints: List[EndpointCoverage] = Field(default_factory=list[EndpointCoverage])
    summary_stats: Dict[str, float] = Field(default_factory=dict[str, float])
