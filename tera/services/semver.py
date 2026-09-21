import re
import json
import yaml
from pathlib import Path
from typing import Tuple, List, Dict, Any, cast
from tera.domain import SchemaDiff, SemverResult
from tera.exceptions import TeraError

SEMVER_REGEX = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

class SemverService:
    """
    Service responsible for analyzing semantic diffs and recommending SemVer bumps.
    """

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, int, int]:
        """
        Parses a SemVer string into a tuple of (major, minor, patch).
        Raises TeraError if the format is invalid.
        """
        match = SEMVER_REGEX.match(version_str.strip())
        if not match:
            raise TeraError(
                "Invalid SemVer Format",
                f"Version '{version_str}' does not conform to semantic versioning (expected MAJOR.MINOR.PATCH)."
            )

        major = int(match.group("major"))
        minor = int(match.group("minor"))
        patch = int(match.group("patch"))
        return major, minor, patch

    def calculate_bump(self, diff: SchemaDiff, current_version: str) -> SemverResult:
        """
        Calculates the recommended SemVer bump and next version from a SchemaDiff.
        """
        major, minor, patch = self.parse_version(current_version)

        if diff.is_empty:
            return SemverResult(
                current_version=current_version,
                bump="none",
                next_version=current_version,
                reasons=["No changes detected between specifications."],
                breaking_count=0
            )

        if diff.has_breaking_changes:
            reasons: List[str] = [f"{diff.breaking_count} breaking change(s) detected:"]
            # Collect sample reasons
            for change in diff.api_changes:
                if change.impact == "breaking":
                    reasons.append(f"API: {change.description}")

            for ep in diff.endpoint_diffs:
                if ep.impact == "breaking":
                    if ep.kind == "removed":
                        reasons.append(f"Endpoint removed: {ep.method} {ep.path}")
                    else:
                        for c in ep.changes:
                            if c.impact == "breaking":
                                reasons.append(f"{ep.method} {ep.path}: {c.description}")

            return SemverResult(
                current_version=current_version,
                bump="major",
                next_version=f"{major + 1}.0.0",
                reasons=reasons,
                breaking_count=diff.breaking_count
            )

        # Check for additions (minor bump)
        has_additions = False
        addition_reasons: List[str] = []

        for ep in diff.endpoint_diffs:
            if ep.kind == "added":
                has_additions = True
                addition_reasons.append(f"Added new endpoint: {ep.method} {ep.path}")
            elif ep.kind == "modified":
                for c in ep.changes:
                    if c.kind == "added":
                        has_additions = True
                        addition_reasons.append(f"{ep.method} {ep.path}: {c.description}")

        for change in diff.api_changes:
            if change.kind == "added":
                has_additions = True
                addition_reasons.append(f"API: {change.description}")

        if has_additions:
            reasons = ["Backwards-compatible features added:"] + addition_reasons
            return SemverResult(
                current_version=current_version,
                bump="minor",
                next_version=f"{major}.{minor + 1}.0",
                reasons=reasons,
                breaking_count=0
            )

        # Only non-breaking modifications (patch bump)
        patch_reasons: List[str] = ["Backwards-compatible metadata and documentation fixes:"]
        for change in diff.api_changes:
            patch_reasons.append(f"API: {change.description}")
        for ep in diff.endpoint_diffs:
            for c in ep.changes:
                patch_reasons.append(f"{ep.method} {ep.path}: {c.description}")

        return SemverResult(
            current_version=current_version,
            bump="patch",
            next_version=f"{major}.{minor}.{patch + 1}",
            reasons=patch_reasons,
            breaking_count=0
        )

    def apply_bump(self, file_path: Path, new_version: str) -> None:
        """
        Updates the version field directly in the target specification file.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Cannot bump version: file '{file_path}' does not exist.")

        raw_content = file_path.read_text(encoding="utf-8")

        if file_path.suffix == ".json":
            try:
                parsed_json = json.loads(raw_content)
                if isinstance(parsed_json, dict) and "api" in parsed_json and isinstance(parsed_json["api"], dict):
                    parsed_json["api"]["version"] = new_version
                    file_path.write_text(json.dumps(parsed_json, indent=2), encoding="utf-8")
                    return
            except Exception as e:
                raise TeraError("JSON Update Error", f"Could not update version in JSON file: {e}")

        # For YAML, attempt regex replacement to preserve comments
        pattern = re.compile(r'(api:\s*\n(?:[ \t]*[^\n#]*\n)*?[ \t]*version:\s*)["\']?[^"\'\r\n]+["\']?')
        if pattern.search(raw_content):
            updated_content = pattern.sub(rf'\g<1>"{new_version}"', raw_content, count=1)
            file_path.write_text(updated_content, encoding="utf-8")
            return

        # Fallback to YAML parse and dump
        try:
            parsed_yaml: Any = yaml.safe_load(raw_content)
            if isinstance(parsed_yaml, dict) and "api" in parsed_yaml and isinstance(parsed_yaml["api"], dict):
                dict_yaml = cast(Dict[str, Any], parsed_yaml)
                api_dict = cast(Dict[str, Any], dict_yaml["api"])
                api_dict["version"] = new_version
                with open(file_path, "w", encoding="utf-8") as f:
                    yaml.dump(dict_yaml, f, sort_keys=False, default_flow_style=False)
                return
        except Exception as e:
            raise TeraError("YAML Update Error", f"Could not update version in YAML file: {e}")

        raise TeraError("Version Update Failed", f"Could not locate 'api.version' inside '{file_path}'.")
