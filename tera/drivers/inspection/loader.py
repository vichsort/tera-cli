import sys
import os
import importlib
import importlib.util
from pathlib import Path
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
    
    file_path = Path(module_name)
    if file_path.suffix == ".py" or file_path.is_file():
        if not file_path.exists():
            raise ImportError(
                f"Could not find Python file '{file_path}'. "
                "Make sure the path is correct."
            )
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for '{file_path}'.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[file_path.stem] = module
        spec.loader.exec_module(module)
    else:
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