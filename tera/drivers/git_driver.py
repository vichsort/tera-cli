import json
import subprocess
from typing import Any, Dict, cast
import yaml

from tera.contracts import TeraDriver
from tera.domain import TeraSchema
from tera.exceptions import TeraError


class GitFileDriver(TeraDriver):
    """
    Input driver that reads a specification from a git revision.
    Executes 'git show <rev>:<file_path>' and parses it into a TeraSchema.
    """

    def __init__(self, revision: str, file_path: str = "docs.yaml") -> None:
        self.revision = revision
        self.file_path = file_path

    def load(self) -> TeraSchema:
        try:
            result = subprocess.run(
                ["git", "show", f"{self.revision}:{self.file_path}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                err_msg = (
                    result.stderr.strip()
                    or f"Revision '{self.revision}' or file '{self.file_path}' not found in git."
                )
                raise TeraError(
                    "Git Reference Error",
                    f"Could not read '{self.file_path}' from git revision '{self.revision}': {err_msg}",
                )

            raw_text = result.stdout
            if self.file_path.endswith(".json"):
                parsed: Any = json.loads(raw_text)
            else:
                parsed = yaml.safe_load(raw_text)

            if not isinstance(parsed, dict):
                raise TeraError(
                    "Schema Load Error",
                    f"Content in git revision '{self.revision}:{self.file_path}' is not a valid object.",
                )

            data_dict = cast(Dict[str, Any], parsed)

            # Support OpenAPI specs stored in git
            if "openapi" in data_dict or "swagger" in data_dict:
                from tera.drivers.openapi_driver import OpenApiDriver

                return OpenApiDriver(data_dict).load()

            return TeraSchema.model_validate(data_dict)

        except FileNotFoundError:
            raise TeraError(
                "Git Unavailable",
                "Git command line tool is not available in the current environment.",
            )
        except Exception as e:
            if isinstance(e, TeraError):
                raise
            raise TeraError(
                "Schema Load Error",
                f"Failed to parse schema from '{self.revision}:{self.file_path}': {str(e)}",
            )
