from datetime import date
from typing import List
from pydantic import BaseModel, ConfigDict, Field

class ChangelogSection(BaseModel):
    """
    Represents a single release section in Keep a Changelog format.
    """
    model_config = ConfigDict(extra='forbid')

    version: str
    release_date: str = Field(default_factory=lambda: date.today().isoformat())
    added: List[str] = Field(default_factory=list[str])
    changed: List[str] = Field(default_factory=list[str])
    deprecated: List[str] = Field(default_factory=list[str])
    removed: List[str] = Field(default_factory=list[str])
    security: List[str] = Field(default_factory=list[str])

    def to_markdown(self) -> str:
        """
        Renders the section in Keep a Changelog Markdown format.
        """
        lines: List[str] = [f"## [{self.version}] - {self.release_date}"]

        sections = [
            ("Added", self.added),
            ("Changed", self.changed),
            ("Deprecated", self.deprecated),
            ("Removed", self.removed),
            ("Security", self.security),
        ]

        has_entries = False
        for title, entries in sections:
            if entries:
                has_entries = True
                lines.append(f"\n### {title}")
                for entry in entries:
                    lines.append(f"- {entry}")

        if not has_entries:
            lines.append("\n- No API changes recorded.")

        return "\n".join(lines)
