import sys
import os
import importlib
from typing import Any

def load_app_instance(import_string: str) -> Any:
    """
    Dynamically imports an application instance from a string.

    Args:
        import_string: format 'module:attr' (e.g.: 'src.main:app')
        
    Returns:
        The python object loaded (e.g., the Flask instance).
        
    Raises:
        ValueError: If the string format is incorrect.
        ImportError: If the module cannot be found.
        AttributeError: If the attribute does not exist in the module.
    """
    if ":" not in import_string:
        raise ValueError(
            f"Invalid import format: '{import_string}'. "
            "Use 'module:attribute' format (e.g., 'main:app')."
        )
    
    module_name, attr_name = import_string.split(":", 1)
    
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise ImportError(
            f"Could not import module '{module_name}'. "
            f"Make sure you are in the project root and the file exists.\nDetails: {e}"
        )
    
    try:
        instance = getattr(module, attr_name)
    except AttributeError:
        raise AttributeError(
            f"Module '{module_name}' loaded successfully, but has no attribute '{attr_name}'."
        )
        
    return instance