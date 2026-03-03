"""Istari functions offered by the module. A function here is a business construct, and not related to programming languages."""

import importlib
import logging
import pkgutil
import sys
from typing import Iterable

from module.functions.registry import FUNCTIONS

logger = logging.getLogger(__name__)

# Import all function modules so they register themselves
# This ensures functions are available when the module is imported


def load_modules_from_package(package_path: Iterable[str]) -> None:
    """
    Dynamically loads modules from the package specified. Does not recurse.

    :param package_path: The path to the package to import modules from.
    """
    logger.info(f"Scanning package path: {package_path}")
    count = 0
    for loader, module_name, is_pkg in pkgutil.iter_modules(package_path):
        if (
            is_pkg
            or module_name in sys.modules
            or module_name == "base"
            or module_name == "registry"
        ):
            continue
        try:
            logger.info(f"Loading module: {module_name}")
            importlib.import_module(f"{__name__}.{module_name}")
            count += 1
        except Exception as e:
            logger.error(f"Failed to load module {module_name}: {e}")

    logger.info(f"Loaded {count} modules")


load_modules_from_package(__path__)

# Export the registry for easy access
__all__ = ["FUNCTIONS"]
