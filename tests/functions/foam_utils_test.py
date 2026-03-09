"""
Unit tests for module/services/foam_utils.py

Covers:
- validate_case_structure()
- read_of_value() / write_of_value()
- parse_solver_log()
- read_foam_job()
- unzip_case()
"""

import zipfile
from pathlib import Path

import pytest

from module.services.foam_utils import (
    infer_run_config,
    read_of_value,
    parse_solver_log,
    unzip_case,
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
# infer_run_config
# ---------------------------------------------------------------------------

def _make_minimal_case(case_dir: Path) -> None:
    """Create a minimal valid OpenFOAM case directory structure."""
    (case_dir / "0").mkdir(parents=True)
    (case_dir / "constant").mkdir()
    system = case_dir / "system"
    system.mkdir()
    (system / "controlDict").write_text("endTime 1;")
    (system / "fvSchemes").write_text("")
    (system / "fvSolution").write_text("")


def test_infer_run_config_no_optional_files(tmp_path):
    """No blockMeshDict/snappyHexMeshDict/setFieldsDict/decomposeParDict → all False."""
    case = tmp_path / "cavity"
    _make_minimal_case(case)

    config = infer_run_config(case)
    assert config["run_blockmesh"] is False
    assert config["run_snappy"] is False
    assert config["run_set_fields"] is False
    assert config["parallel"] is False
    assert config["np"] == 1


def test_infer_run_config_blockmesh_detected(tmp_path):
    """blockMeshDict present → run_blockmesh=True."""
    case = tmp_path / "cavity"
    _make_minimal_case(case)
    (case / "system" / "blockMeshDict").write_text("")

    config = infer_run_config(case)
    assert config["run_blockmesh"] is True


def test_infer_run_config_parallel_from_decompose_par_dict(tmp_path):
    """decomposeParDict with numberOfSubdomains 4 → parallel=True, np=4."""
    case = tmp_path / "cavity"
    _make_minimal_case(case)
    (case / "system" / "decomposeParDict").write_text("numberOfSubdomains 4;")

    config = infer_run_config(case)
    assert config["parallel"] is True
    assert config["np"] == 4


def test_infer_run_config_serial_with_decompose_par_dict(tmp_path):
    """decomposeParDict with numberOfSubdomains 1 → parallel=False."""
    case = tmp_path / "cavity"
    _make_minimal_case(case)
    (case / "system" / "decomposeParDict").write_text("numberOfSubdomains 1;")

    config = infer_run_config(case)
    assert config["parallel"] is False
    assert config["np"] == 1


# ---------------------------------------------------------------------------
# unzip_case
# ---------------------------------------------------------------------------

def _make_case_zip(zip_path: Path, case_dir_name: str | None = None,
                   extra_dirs: list[str] | None = None) -> None:
    """
    Helper: create a minimal .foam.zip with system/controlDict.

    If case_dir_name is given, files are wrapped inside that directory
    (e.g. airFoil2D/system/controlDict).  Otherwise they are at the root.
    Extra top-level directories (e.g. '__MACOSX') can be added via extra_dirs.
    """
    prefix = f"{case_dir_name}/" if case_dir_name else ""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{prefix}system/controlDict", "endTime 1;")
        zf.writestr(f"{prefix}system/fvSchemes", "")
        zf.writestr(f"{prefix}system/fvSolution", "")
        zf.writestr(f"{prefix}constant/", "")
        zf.writestr(f"{prefix}0/", "")
        for d in (extra_dirs or []):
            zf.writestr(f"{d}/.keep", "")


def test_unzip_case_flat_structure(tmp_path):
    """Flat zip (system/controlDict at root) returns dest_dir directly."""
    zip_path = tmp_path / "case.foam.zip"
    _make_case_zip(zip_path)

    result = unzip_case(str(zip_path), str(tmp_path / "out"))
    assert (result / "system" / "controlDict").exists()


def test_unzip_case_wrapped_structure(tmp_path):
    """Wrapped zip (airFoil2D/system/controlDict) returns the inner directory."""
    zip_path = tmp_path / "case.foam.zip"
    _make_case_zip(zip_path, case_dir_name="airFoil2D")

    result = unzip_case(str(zip_path), str(tmp_path / "out"))
    assert result.name == "airFoil2D"
    assert (result / "system" / "controlDict").exists()


def test_unzip_case_macosx_ignored(tmp_path):
    """__MACOSX directory is ignored; the single real case dir is returned."""
    zip_path = tmp_path / "case.foam.zip"
    _make_case_zip(zip_path, case_dir_name="airFoil2D", extra_dirs=["__MACOSX"])

    result = unzip_case(str(zip_path), str(tmp_path / "out"))
    assert result.name == "airFoil2D"
    assert (result / "system" / "controlDict").exists()


def test_unzip_case_macosx_with_flat_structure(tmp_path):
    """__MACOSX in a flat zip does not confuse the flat-structure check."""
    zip_path = tmp_path / "case.foam.zip"
    _make_case_zip(zip_path, extra_dirs=["__MACOSX"])

    result = unzip_case(str(zip_path), str(tmp_path / "out"))
    assert (result / "system" / "controlDict").exists()
