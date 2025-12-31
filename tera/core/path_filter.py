import pathspec
from typing import List, Union
from pathlib import Path

DEFAULT_IGNORES = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "*.pyc",
    ".env",
    ".teraconfig.toml",
    "teraignore",
    "site-packages",
    "node_modules"
]

class PathFilter:
    """
    Responsible for determining whether a file or directory should be ignored.
    Uses 'gitwildmatch' syntax (same as .gitignore).
    """
    def __init__(self, user_patterns: List[str] = None):
        patterns = set(DEFAULT_IGNORES)
        if user_patterns:
            patterns.update(user_patterns)

        self.spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    def should_ignore(self, path: Union[str, Path]) -> bool:
        """
        Returns True if the path should be ignored based on the ignore patterns.
        """
        clean_path = str(path)
        return self.spec.match_file(clean_path)