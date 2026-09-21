import json
import yaml
import subprocess
from pathlib import Path
from typing import Union, Dict, Any, cast
from tera.domain import TeraSchema, LintSeverity
from tera.adapters import FileLoader
from tera.exceptions import TeraError

def load_schema_from_source(source: Union[str, Path]) -> TeraSchema:
    """
    Loads a TeraSchema instance from either a local file or a git revision reference.
    
    Supported formats:
      - Local paths: 'docs.yaml', 'docs.v1.json', Path('docs.yaml')
      - Git revisions: 'git:HEAD~1:docs.yaml', 'HEAD~1:docs.yaml', 'HEAD:docs.yaml'
    """
    source_str = str(source)
    local_path = Path(source_str)

    if local_path.exists() and local_path.is_file():
        data, issues = FileLoader.load(local_path)
        for issue in issues:
            if issue.severity == LintSeverity.ERROR:
                raise TeraError("Schema Load Error", f"Error loading '{source_str}': {issue.message}")
        if data is None:
            raise TeraError("Schema Load Error", f"File '{source_str}' is empty or invalid.")
        return TeraSchema.model_validate(data)

    # Check for git reference syntax
    is_git_prefixed = source_str.startswith("git:")
    if is_git_prefixed or (":" in source_str and not local_path.exists()):
        git_target = source_str[4:] if is_git_prefixed else source_str
        parts = git_target.split(":", 1)
        rev = parts[0]
        file_path = parts[1] if len(parts) > 1 else "docs.yaml"

        try:
            result = subprocess.run(
                ["git", "show", f"{rev}:{file_path}"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                err_msg = result.stderr.strip() or f"Revision '{rev}' or file '{file_path}' not found in git."
                raise TeraError("Git Reference Error", f"Could not read '{file_path}' from git revision '{rev}': {err_msg}")

            raw_text = result.stdout
            if file_path.endswith(".json"):
                parsed: Any = json.loads(raw_text)
            else:
                parsed = yaml.safe_load(raw_text)

            if not isinstance(parsed, dict):
                raise TeraError("Schema Load Error", f"Content in git revision '{rev}:{file_path}' is not a valid object.")

            data_dict = cast(Dict[str, Any], parsed)
            return TeraSchema.model_validate(data_dict)

        except FileNotFoundError:
            raise TeraError("Git Unavailable", "Git command line tool is not available in the current environment.")
        except Exception as e:
            if isinstance(e, TeraError):
                raise
            raise TeraError("Schema Load Error", f"Failed to parse schema from '{source_str}': {str(e)}")

    raise FileNotFoundError(f"Specification file not found: '{source_str}'")
