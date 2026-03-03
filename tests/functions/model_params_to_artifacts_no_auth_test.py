import json
from pathlib import Path
from typing import List

import pytest

from module.functions.base.function_io import Output
from module.functions.model_params_to_artifacts_no_auth import (
    model_params_to_artifacts_no_auth,
)


def test_model_params_to_artifacts_no_auth_with_all_params(tmp_path: Path):
    """Test that function works with all parameters specified."""
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()
    (case_dir / "0").mkdir()
    (case_dir / "constant").mkdir()
    (case_dir / "system").mkdir()

    input_message = {
        "case": {
            "type": "user_model",
            "value": str(case_dir),
        },
        "n_processors": {
            "type": "parameter",
            "value": 4,
        },
        "include_summary": {
            "type": "parameter",
            "value": True,
        },
        "output_format": {
            "type": "parameter",
            "value": "vtk",
        },
    }
    input_json = json.dumps(input_message)

    outputs: List[Output] = model_params_to_artifacts_no_auth(input_json, str(tmp_path))

    assert len(outputs) == 3
    names = {o.name for o in outputs}
    assert names == {"summary", "results", "log"}
    for output in outputs:
        assert Path(output.path).exists()


def test_model_params_to_artifacts_no_auth_without_summary(tmp_path: Path):
    """Test that summary is excluded when include_summary is False."""
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()

    input_message = {
        "case": {
            "type": "user_model",
            "value": str(case_dir),
        },
        "include_summary": {
            "type": "parameter",
            "value": False,
        },
    }
    input_json = json.dumps(input_message)

    outputs = model_params_to_artifacts_no_auth(input_json, str(tmp_path))

    assert len(outputs) == 2
    names = {o.name for o in outputs}
    assert "summary" not in names
    assert "results" in names
    assert "log" in names


def test_model_params_to_artifacts_no_auth_with_n_processors(tmp_path: Path):
    """Test that n_processors parameter is accepted."""
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()

    input_message = {
        "case": {"type": "user_model", "value": str(case_dir)},
        "n_processors": {"type": "parameter", "value": 8},
        "include_summary": {"type": "parameter", "value": False},
    }
    input_json = json.dumps(input_message)

    outputs = model_params_to_artifacts_no_auth(input_json, str(tmp_path))

    assert len(outputs) == 2


def test_model_params_to_artifacts_no_auth_without_parameters(tmp_path: Path):
    """Test that function works without parameters (uses defaults)."""
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()

    input_message = {
        "case": {
            "type": "user_model",
            "value": str(case_dir),
        },
    }
    input_json = json.dumps(input_message)

    outputs = model_params_to_artifacts_no_auth(input_json, str(tmp_path))

    assert len(outputs) == 3


def test_model_params_to_artifacts_no_auth_with_output_format(tmp_path: Path):
    """Test that output_format parameter affects results file extension."""
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()

    input_message = {
        "case": {"type": "user_model", "value": str(case_dir)},
        "output_format": {"type": "parameter", "value": "csv"},
        "include_summary": {"type": "parameter", "value": False},
    }
    input_json = json.dumps(input_message)

    outputs = model_params_to_artifacts_no_auth(input_json, str(tmp_path))

    results_output = next(o for o in outputs if o.name == "results")
    assert results_output.path.endswith(".csv")


def test_model_params_to_artifacts_no_auth_with_invalid_input():
    """Test that function raises ValueError with invalid input."""
    invalid_json = '{"invalid": "input"}'
    with pytest.raises(ValueError, match="Invalid input"):
        model_params_to_artifacts_no_auth(invalid_json, "/tmp")


def test_model_params_to_artifacts_no_auth_with_nonexistent_case(tmp_path: Path):
    """Test that function raises ValueError when case path does not exist."""
    input_message = {
        "case": {
            "type": "user_model",
            "value": str(tmp_path / "nonexistent_case"),
        },
    }
    input_json = json.dumps(input_message)

    with pytest.raises(ValueError):
        model_params_to_artifacts_no_auth(input_json, str(tmp_path))


def test_model_params_to_artifacts_no_auth_with_tgz_archive(tmp_path: Path):
    """Test that .tgz case archive is extracted and processed."""
    import tarfile

    case_dir = tmp_path / "case_src"
    case_dir.mkdir()
    (case_dir / "0").mkdir()
    (case_dir / "system").mkdir()

    archive_path = tmp_path / "case.tgz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(case_dir, arcname="cavity")

    input_message = {
        "case": {"type": "user_model", "value": str(archive_path)},
        "include_summary": {"type": "parameter", "value": False},
    }
    input_json = json.dumps(input_message)

    outputs = model_params_to_artifacts_no_auth(input_json, str(tmp_path))

    assert len(outputs) == 2
