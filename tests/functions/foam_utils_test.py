"""
Unit tests for lib/foam_utils.py

Covers:
- validate_case_structure()
- read_of_value() / write_of_value()
- parse_solver_log()
- read_foam_job()
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure lib/ is on the path (tests/functions/ → tests/ → open-foam-module/ → lib/)
_LIB_DIR = str(Path(__file__).parents[2] / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from foam_utils import (
    read_foam_job,
    read_of_value,
    parse_solver_log,
    validate_case_structure,
    write_of_value,
)


# ---------------------------------------------------------------------------
# validate_case_structure
# ---------------------------------------------------------------------------

def test_validate_case_structure_valid(tmp_path):
    """A complete case directory passes with no issues."""
    case = tmp_path / "cavity"
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    system = case / "system"
    system.mkdir()
    (system / "controlDict").write_text("endTime 1;")
    (system / "fvSchemes").write_text("")
    (system / "fvSolution").write_text("")

    issues = validate_case_structure(case)
    assert issues == []


def test_validate_case_structure_missing_dir(tmp_path):
    """Missing '0/' is reported as an issue."""
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    (case / "system").mkdir()
    (case / "system" / "controlDict").write_text("")
    (case / "system" / "fvSchemes").write_text("")
    (case / "system" / "fvSolution").write_text("")

    issues = validate_case_structure(case)
    assert any("0/" in issue for issue in issues)


def test_validate_case_structure_missing_system_file(tmp_path):
    """Missing fvSchemes is reported."""
    case = tmp_path / "cavity"
    (case / "0").mkdir(parents=True)
    (case / "constant").mkdir()
    system = case / "system"
    system.mkdir()
    (system / "controlDict").write_text("")
    (system / "fvSolution").write_text("")
    # fvSchemes intentionally missing

    issues = validate_case_structure(case)
    assert any("fvSchemes" in issue for issue in issues)


# ---------------------------------------------------------------------------
# read_of_value / write_of_value
# ---------------------------------------------------------------------------

CONTROL_DICT_SAMPLE = """\
/*--------------------------------*- C++ -*----------------------------------*\\
FoamFile
{
    format      ascii;
    class       dictionary;
    object      controlDict;
}
application     foamRun;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         0.5;
deltaT          0.005;
writeInterval   0.1;
"""


def test_read_of_value_present(tmp_path):
    """read_of_value returns the correct value for a present key."""
    f = tmp_path / "controlDict"
    f.write_text(CONTROL_DICT_SAMPLE)
    assert read_of_value(f, "endTime") == "0.5"
    assert read_of_value(f, "application") == "foamRun"


def test_read_of_value_missing_key(tmp_path):
    """read_of_value returns None when the key is not in the file."""
    f = tmp_path / "controlDict"
    f.write_text(CONTROL_DICT_SAMPLE)
    assert read_of_value(f, "nonExistentKey") is None


def test_write_of_value_success(tmp_path):
    """write_of_value updates an existing key and returns True."""
    f = tmp_path / "controlDict"
    f.write_text(CONTROL_DICT_SAMPLE)
    result = write_of_value(f, "endTime", "2.0")
    assert result is True
    assert read_of_value(f, "endTime") == "2.0"


def test_write_of_value_missing_key(tmp_path):
    """write_of_value returns False when the key does not exist."""
    f = tmp_path / "controlDict"
    f.write_text(CONTROL_DICT_SAMPLE)
    result = write_of_value(f, "nonExistentKey", "42")
    assert result is False


# ---------------------------------------------------------------------------
# parse_solver_log
# ---------------------------------------------------------------------------

SOLVER_LOG_CONVERGED = """\
Time = 0.1
Solving for Ux, Initial residual = 0.1, Final residual = 1e-06, No Iterations 3
Solving for p, Initial residual = 0.3, Final residual = 2e-06, No Iterations 5
ExecutionTime = 1.2 s

Time = 0.2
Solving for Ux, Initial residual = 0.05, Final residual = 5e-07, No Iterations 2
Solving for p, Initial residual = 0.1, Final residual = 1e-06, No Iterations 3
ExecutionTime = 2.1 s

End

ExecutionTime = 2.1 s
"""

SOLVER_LOG_FAILED = """\
Time = 0.1
Solving for Ux, Initial residual = 0.9, Final residual = 0.5, No Iterations 100
"""


def test_parse_solver_log_converged():
    """Logs containing 'End' are marked converged=True."""
    result = parse_solver_log(SOLVER_LOG_CONVERGED)
    assert result["converged"] is True
    assert "Ux" in result["final_residuals"]
    assert "p" in result["final_residuals"]
    assert result["execution_time_seconds"] == pytest.approx(2.1)
    assert 0.1 in result["time_steps"]
    assert 0.2 in result["time_steps"]


def test_parse_solver_log_not_converged():
    """Logs without an 'End' marker are marked converged=False."""
    result = parse_solver_log(SOLVER_LOG_FAILED)
    assert result["converged"] is False


def test_parse_solver_log_empty():
    """Empty log returns safe defaults."""
    result = parse_solver_log("")
    assert result["converged"] is False
    assert result["final_residuals"] == {}
    assert result["time_steps"] == []
    assert result["execution_time_seconds"] is None


# ---------------------------------------------------------------------------
# read_foam_job
# ---------------------------------------------------------------------------

VALID_JOB = {
    "case_name": "cavity_test",
    "foam_version": "13",
    "solver_module": "incompressibleFluid",
    "mesh_required": True,
    "parallel": False,
    "np": 1,
}


def test_read_foam_job_valid(tmp_path):
    """Valid foam_job.json is read and returned with defaults applied."""
    case = tmp_path / "cavity"
    case.mkdir()
    (case / "foam_job.json").write_text(json.dumps(VALID_JOB))

    job = read_foam_job(case)
    assert job["case_name"] == "cavity_test"
    assert job["foam_version"] == "13"
    assert job["solver_module"] == "incompressibleFluid"
    # Defaults applied
    assert "post_process" in job
    assert "result_fields" in job
    assert "tags" in job


def test_read_foam_job_missing_file(tmp_path):
    """FileNotFoundError raised when foam_job.json does not exist."""
    case = tmp_path / "cavity"
    case.mkdir()

    with pytest.raises(FileNotFoundError, match="foam_job.json"):
        read_foam_job(case)


def test_read_foam_job_missing_required_keys(tmp_path):
    """ValueError raised when required keys are absent."""
    case = tmp_path / "cavity"
    case.mkdir()
    incomplete = {"case_name": "test"}  # missing foam_version, solver_module
    (case / "foam_job.json").write_text(json.dumps(incomplete))

    with pytest.raises(ValueError, match="missing required keys"):
        read_foam_job(case)
