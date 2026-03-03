"""
Simple function registry for Istari functions.

Functions are registered by adding them to the FUNCTIONS dictionary.
"""

from typing import Callable, Dict

from module.functions.base.function_io import Output

# Type alias for function signature
FunctionType = Callable[[str, str], list[Output]]

# Registry of all available functions
FUNCTIONS: Dict[str, FunctionType] = {}


def register(name: str, func: FunctionType) -> None:
    """
    Register a function with the given name.

    :param name: The function name (must match module_manifest.json).
    :param func: The function to register.
    """
    FUNCTIONS[name] = func


def get_function(name: str) -> FunctionType:
    """
    Get a function by name.

    :param name: The function name.
    :return: The function.
    :raises ValueError: If the function name is not registered.
    """
    if name not in FUNCTIONS:
        raise ValueError(f'Function "{name}" is not registered.')
    return FUNCTIONS[name]
