import pytest

# Import functions module to trigger registration
import module.functions  # noqa: F401
from module.functions.registry import get_function


def test_get_run_foam():
    function = get_function("run_foam")
    assert callable(function)
    assert function.__name__ == "run_foam"


def test_get_inspect_foam():
    function = get_function("inspect_foam")
    assert callable(function)
    assert function.__name__ == "inspect_foam"


def test_get_patch_foam():
    function = get_function("patch_foam")
    assert callable(function)
    assert function.__name__ == "patch_foam"


def test_get_function_from_unknown_name():
    with pytest.raises(ValueError, match="not registered"):
        get_function("invalid function name")
