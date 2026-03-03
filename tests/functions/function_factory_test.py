import pytest

# Import functions module to trigger registration
import module.functions  # noqa: F401
from module.functions.registry import get_function


def test_get_function():
    """
    Valid function names should return the correct function.
    """
    function = get_function("ModelParamsToArtifactsNoAuth")
    assert callable(function)
    assert function.__name__ == "model_params_to_artifacts_no_auth"


def test_get_function_from_unknown_name():
    """
    Invalid function names should raise ValueError.
    """
    with pytest.raises(ValueError, match="not registered"):
        get_function("invalid function name")
