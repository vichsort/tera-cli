import inspect
from typing import Callable, Any, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class DocStringInfo:
    summary: str
    description: Optional[str] = None

@dataclass
class FunctionSignature:
    parameters: Dict[str, Any] = field(default_factory=dict)
    has_kwargs: bool = False

def parse_docstring(func: Callable) -> DocStringInfo:
    """
    Extract and cleans the function's docstring.
    Separates the first line (Summary) from the rest (Description).
    """
    raw_doc = inspect.getdoc(func)
    
    if not raw_doc:
        return DocStringInfo(summary="No summary available")

    lines = raw_doc.strip().split('\n')
    summary = lines[0].strip()

    description = None
    if len(lines) > 1:
        rest = "\n".join(lines[1:]).strip()
        if rest:
            description = rest

    return DocStringInfo(summary=summary, description=description)

def parse_signature(func: Callable) -> FunctionSignature:
    """
    Inspects the function signature to extract Type Hints.
    """
    try:
        sig = inspect.signature(func)
    except ValueError:
        return FunctionSignature()

    params = {}
    has_kwargs = False

    for name, param in sig.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            has_kwargs = True
            continue

        if name in ('self', 'cls'):
            continue

        annotation = param.annotation

        if annotation == inspect.Parameter.empty:
            annotation = None
            
        params[name] = annotation

    return FunctionSignature(parameters=params, has_kwargs=has_kwargs)