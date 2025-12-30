import ast
import inspect
import textwrap
from typing import List, Callable, Any

def get_decorators(func: Callable) -> List[str]:
    """
    Analises the code and returns an list with the names
    of decorators applied to it.
    
    e.g.:
        @app.route(...)
        @jwt_required()
        def minha_func(): ...
        
    Returns:
        ['app.route', 'jwt_required']
    """
    try:
        source = inspect.getsource(func)
        source = textwrap.dedent(source)
        tree = ast.parse(source)
        
    except (OSError, TypeError, SyntaxError):
        return []

    decorators = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator_node in node.decorator_list:
                dec_name = _extract_decorator_name(decorator_node)
                if dec_name:
                    decorators.append(dec_name)
            break
            
    return decorators

def _extract_decorator_name(node: Any) -> str:
    """
    Extracts legible name from an AST decorator node.
    Handles: @auth, @auth(), @module.auth
    """
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        return _get_attribute_name(node)

    if isinstance(node, ast.Call):
        return _extract_decorator_name(node.func)
        
    return ""

def _get_attribute_name(node: ast.Attribute) -> str:
    """Reconstruct complete names as 'bp.route'."""
    prefix = ""
    if isinstance(node.value, ast.Name):
        prefix = node.value.id
    elif isinstance(node.value, ast.Attribute):
        prefix = _get_attribute_name(node.value)
        
    return f"{prefix}.{node.attr}"