import json
import yaml
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, TextIO, cast
from tera.domain.linting import LintIssue, LintSeverity

class FileLoader:
    """
    Adapter responsible for safe I/O.
    Reads files and returns raw data or syntax issues. 
    """   
    @staticmethod
    def load(path: Path) -> Tuple[Optional[Dict[str, Any]], list[LintIssue]]:
        issues: list[LintIssue] = []
        
        if not path.exists():
            issues.append(LintIssue(
                code="file_not_found", message=f"File not found: {path}", severity=LintSeverity.ERROR
            ))
            return None, issues

        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix in ['.yaml', '.yml']:
                    return FileLoader._parse_yaml(f)
                elif path.suffix == '.json':
                    return FileLoader._parse_json(f)
                else:
                    issues.append(LintIssue(
                        code="unknown_format", message="Unsupported extension.", severity=LintSeverity.ERROR
                    ))
                    return None, issues
        except Exception as e:
            issues.append(LintIssue(
                code="io_error", message=str(e), severity=LintSeverity.ERROR
            ))
            return None, issues

    @staticmethod
    def _parse_yaml(stream: TextIO) -> Tuple[Optional[Dict[str, Any]], list[LintIssue]]:
        try:
            raw_data: Any = yaml.safe_load(stream)
            data: Optional[Dict[str, Any]] = cast(Optional[Dict[str, Any]], raw_data) if isinstance(raw_data, dict) else None
            return data, []
        except yaml.YAMLError as e:
            line: Optional[int] = None
            mark: Any = getattr(e, 'problem_mark', None)
            if mark is not None and hasattr(mark, 'line'):
                line = int(mark.line) + 1
            return None, [LintIssue(
                code="yaml_syntax", message=f"Invalid YAML: {e}", severity=LintSeverity.ERROR, line=line
            )]

    @staticmethod
    def _parse_json(stream: TextIO) -> Tuple[Optional[Dict[str, Any]], list[LintIssue]]:
        try:
            raw_data: Any = json.load(stream)
            data: Optional[Dict[str, Any]] = cast(Optional[Dict[str, Any]], raw_data) if isinstance(raw_data, dict) else None
            return data, []
        except json.JSONDecodeError as e:
            return None, [LintIssue(
                code="json_syntax", message=f"Invalid JSON: {e.msg}", severity=LintSeverity.ERROR, line=e.lineno
            )]