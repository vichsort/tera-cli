import re
from datetime import date
from pathlib import Path
from typing import Optional, List
from tera.domain import SchemaDiff, ChangelogSection

CHANGELOG_HEADER = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

"""

class ChangelogService:
    """
    Generates structured Keep a Changelog entries from semantic schema diffs.
    """

    def generate(
        self,
        diff: SchemaDiff,
        version: str,
        release_date: Optional[str] = None
    ) -> ChangelogSection:
        """
        Transforms a SchemaDiff into a ChangelogSection categorized into Keep a Changelog types.
        """
        final_date = release_date or date.today().isoformat()

        added: List[str] = []
        changed: List[str] = []
        deprecated: List[str] = []
        removed: List[str] = []
        security: List[str] = []

        # Process API changes
        for change in diff.api_changes:
            desc = change.description
            if "auth" in change.path:
                security.append(desc)
            elif change.kind == "added":
                added.append(desc)
            elif change.kind == "removed":
                removed.append(desc)
            else:
                changed.append(desc)

        # Process Endpoints
        for ep in diff.endpoint_diffs:
            if ep.kind == "added":
                added.append(f"Added endpoint `{ep.method} {ep.path}`")
            elif ep.kind == "removed":
                removed.append(f"Removed endpoint `{ep.method} {ep.path}`")
            else:
                for c in ep.changes:
                    desc = f"`{ep.method} {ep.path}`: {c.description}"
                    if "auth" in c.path:
                        security.append(desc)
                    elif c.kind == "added":
                        added.append(desc)
                    elif c.kind == "removed":
                        removed.append(desc)
                    else:
                        changed.append(desc)

        return ChangelogSection(
            version=version,
            release_date=final_date,
            added=added,
            changed=changed,
            deprecated=deprecated,
            removed=removed,
            security=security
        )

    def append_to_file(self, changelog_path: Path, section: ChangelogSection) -> None:
        """
        Prepends the new changelog section into an existing or newly created CHANGELOG.md.
        """
        markdown_entry = section.to_markdown()

        if not changelog_path.exists():
            full_content = f"{CHANGELOG_HEADER}{markdown_entry}\n"
            changelog_path.write_text(full_content, encoding="utf-8")
            return

        existing_content = changelog_path.read_text(encoding="utf-8")

        # Find first existing release header "## ["
        match = re.search(r"(?m)^## \[", existing_content)
        if match:
            idx = match.start()
            new_content = f"{existing_content[:idx]}{markdown_entry}\n\n{existing_content[idx:]}"
        else:
            new_content = f"{existing_content.rstrip()}\n\n{markdown_entry}\n"

        changelog_path.write_text(new_content, encoding="utf-8")
