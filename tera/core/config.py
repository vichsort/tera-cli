from pathlib import Path
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

class LintConfig(BaseModel):
    """
    Configuration specific to the Linter.
    """
    model_config = ConfigDict(extra='ignore')
    ignore: List[str] = Field(default_factory=list)

class TeraConfig(BaseModel):
    """
    Typed representation for Tera configurations.
    Can be reconfigured via .teraconfig.toml, CLI args or Env Vars.
    """
    model_config = ConfigDict(extra='ignore')

    target: Optional[str] = Field(None, description="Default import string for scanning.")
    output: Optional[Path] = Field(None, description="Default output path.")
    ignore: List[str] = Field(default_factory=list, description="List of patterns to ignore.")
    format: Literal["json", "yaml"] = Field("yaml", description="Output format preference.")
    title: Optional[str] = None
    version: str = "1.0.0"
    lint: LintConfig = Field(default_factory=LintConfig)