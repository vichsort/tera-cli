from typing import List
from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    """Detailed information about a single validation failure."""

    location: str
    message: str
    error_type: str


class ValidationReport(BaseModel):
    """Result of validating a specification against the canonical Tera IR schema."""

    file_path: str
    is_valid: bool
    errors: List[ValidationErrorDetail] = Field(default_factory=list[ValidationErrorDetail])
