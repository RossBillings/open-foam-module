"""
Unit tests for module/functions/run_foam.py

Covers the full run_foam pipeline using mocked OpenFOAM commands:
- Serial and parallel execution paths
- Pre-processing steps (blockMesh, snappyHexMesh, setFields)
- Input overrides (endTime, np)
- Failure handling at each step
- Output structure and convergence report content
"""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from module.functions.run_foam import run_foam


# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

CONVERGENCE_STUB = {
    "final_residuals": {"p": 1e-6, "Ux": 5e-7},
    "time_steps": [0.1, 0.2],
    "converged": True,
    "execution_time_seconds": 2.0,
    "warnings": [],
    "errors": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_case_dir(base: Path, name: str = "cavity") -> Path:
    """Create a minimal real OpenFOAM case directory structure."""
    case = base / name
    (case / "0").mkdir(parents=True)
    constant = case / "constant"
    constant.mkdir()
    poly_mesh = constant / "polyMesh"
    poly_mesh.mkdir()
    (poly_mesh / "points").write_text("mesh data")  # non-empty mesh
    system = case / "system"
    system.mkdir()
    (system / "controlDict").write_text(
        "application foamRun;\nstartTime 0;\nendTime 1;\n"
        "deltaT 0.01;\nwriteInterval 0.1;\nstartFrom startTime;\nstopAt endTime;\n"
    )
    (system / "fvSchemes").write_text("")
    (system / "fvSolution").write_text("")
    return case


def _base_config(*, parallel=False, np=1, blockmesh=False, snappy=False, setfields=False):
    return {
        "run_blockmesh": blockmesh,
        "run_snappy": snappy,
        "run_set_fields": setfields,
        "parallel": parallel,
        "np": np,
    }


def _input_json(zip_path, **overrides):
    data = {"foam_case": {"value": str(zip_path)}}
    for k, v in overrides.items():
        data[k] = {"value": v}
    return json.dumps(data)


def _all_mocks(case_dir, tmp_path, *, run_cmd_return=(0, "End\n"), config=None,
               time_dirs=None, fields=None):
    """Return a list of patch context managers for a typical successful run."""
    return [
        patch("module.functions.run_foam.unzip_case", return_value=case_dir),
        patch("module.functions.run_foam.infer_run_config",
              return_value=config or _base_config()),
        patch("module.functions.run_foam.validate_case_structure", return_value=[]),
        patch("module.functions.run_foam.run_cmd", return_value=run_cmd_return),
        patch("module.functions.run_foam.list_time_dirs",
              return_value=time_dirs if time_dirs is not None else ["0", "0.1"]),
        patch("module.functions.run_foam.list_fields_at_time",
              return_value=fields if fields is not None else ["U", "p"]),
        patch("module.functions.run_foam.read_control_dict_values", return_value={}),
        patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
        patch("module.functions.run_foam.zip_case",
              return_value=str(tmp_path / "solved.foam.zip")),
    ]


# ---------------------------------------------------------------------------
# Serial success
# ---------------------------------------------------------------------------

class TestRunFoamSerialSuccess:

    def test_run_foam_returns_three_named_outputs(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")),
            patch("module.functions.run_foam.list_time_dirs", return_value=["0", "0.1"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=["U", "p"]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "solved.foam.zip")),
        ):
            outputs = run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        assert len(outputs) == 3
        assert {o.name for o in outputs} == {"solved_case", "run_log", "convergence_report"}

    def test_run_foam_calls_foamrun_once(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")) as mock_cmd,
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        cmds = [c.args[0] for c in mock_cmd.call_args_list]
        assert "foamRun" in cmds

    def test_run_foam_writes_convergence_report_with_last_time(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")),
            patch("module.functions.run_foam.list_time_dirs", return_value=["0", "0.1"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=["U", "p"]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            outputs = run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        report_path = next(o.path for o in outputs if o.name == "convergence_report")
        report = json.loads(Path(report_path).read_text())
        assert report["last_time"] == "0.1"
        assert "U" in report["fields_at_last_time"]

    def test_run_foam_creates_paraview_touch_file(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")),
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert: ParaView touch file created in case dir
        touch_files = list(case_dir.glob("*.foam"))
        assert len(touch_files) == 1


# ---------------------------------------------------------------------------
# Validation failure
# ---------------------------------------------------------------------------

class TestRunFoamValidation:

    def test_run_foam_raises_value_error_when_structure_invalid(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure",
                  return_value=["Missing required directory: 0/"]),
        ):
            with pytest.raises(ValueError, match="Case validation failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))


# ---------------------------------------------------------------------------
# Input overrides
# ---------------------------------------------------------------------------

class TestRunFoamOverrides:

    def test_run_foam_writes_end_time_override_to_control_dict(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.write_of_value") as mock_write,
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")),
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(
                _input_json(tmp_path / "case.zip", override_end_time=5.0),
                str(tmp_path),
            )

        # Assert
        mock_write.assert_any_call(
            case_dir / "system" / "controlDict", "endTime", "5.0"
        )

    def test_run_foam_writes_np_override_to_decompose_par_dict(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)
        dp = case_dir / "system" / "decomposeParDict"
        dp.write_text("numberOfSubdomains 2;\n")

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config(np=2)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.write_of_value") as mock_write,
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")),
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(
                _input_json(tmp_path / "case.zip", override_np=4),
                str(tmp_path),
            )

        # Assert
        mock_write.assert_any_call(dp, "numberOfSubdomains", "4")


# ---------------------------------------------------------------------------
# blockMesh pre-processing
# ---------------------------------------------------------------------------

class TestRunFoamBlockMesh:

    def test_run_foam_calls_blockmesh_when_blockmeshdict_present_and_no_mesh(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)
        shutil.rmtree(case_dir / "constant" / "polyMesh")

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(blockmesh=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")) as mock_cmd,
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        cmds = [c.args[0] for c in mock_cmd.call_args_list]
        assert "blockMesh" in cmds

    def test_run_foam_skips_blockmesh_when_mesh_already_present(self, tmp_path):
        # Arrange — polyMesh with content already exists from _make_case_dir
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(blockmesh=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")) as mock_cmd,
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        cmds = [c.args[0] for c in mock_cmd.call_args_list]
        assert "blockMesh" not in cmds

    def test_run_foam_raises_value_error_when_blockmesh_fails(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)
        shutil.rmtree(case_dir / "constant" / "polyMesh")

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(blockmesh=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(1, "error")),
        ):
            with pytest.raises(ValueError, match="blockMesh failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))


# ---------------------------------------------------------------------------
# snappyHexMesh and setFields pre-processing
# ---------------------------------------------------------------------------

class TestRunFoamPreProcessing:

    def test_run_foam_calls_snappy_when_configured(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(snappy=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")) as mock_cmd,
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        cmds = [c.args[0] for c in mock_cmd.call_args_list]
        assert any("snappyHexMesh" in c for c in cmds)

    def test_run_foam_raises_value_error_when_snappy_fails(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(snappy=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(1, "error")),
        ):
            with pytest.raises(ValueError, match="snappyHexMesh failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

    def test_run_foam_calls_set_fields_when_configured(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(setfields=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")) as mock_cmd,
            patch("module.functions.run_foam.list_time_dirs", return_value=["0"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        cmds = [c.args[0] for c in mock_cmd.call_args_list]
        assert "setFields" in cmds

    def test_run_foam_raises_value_error_when_set_fields_fails(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(setfields=True)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(1, "error")),
        ):
            with pytest.raises(ValueError, match="setFields failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

class TestRunFoamParallel:

    def test_run_foam_parallel_calls_decompose_foamrun_and_reconstruct(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(parallel=True, np=4)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")) as mock_cmd,
            patch("module.functions.run_foam.list_time_dirs", return_value=["0", "1"]),
            patch("module.functions.run_foam.list_fields_at_time", return_value=["U", "p"]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            outputs = run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        cmds = [c.args[0] for c in mock_cmd.call_args_list]
        assert "decomposePar" in cmds
        assert any("foamRun -parallel" in c for c in cmds)
        assert "reconstructPar" in cmds
        assert len(outputs) == 3

    def test_run_foam_raises_value_error_when_decompose_par_fails(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(parallel=True, np=4)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(1, "error")),
        ):
            with pytest.raises(ValueError, match="decomposePar failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

    def test_run_foam_raises_value_error_when_parallel_foamrun_fails(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)
        call_count = {"n": 0}

        def failing_after_decompose(cmd, **kwargs):
            call_count["n"] += 1
            return (0, "ok") if call_count["n"] == 1 else (1, "error")

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config",
                  return_value=_base_config(parallel=True, np=4)),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", side_effect=failing_after_decompose),
        ):
            with pytest.raises(ValueError, match="Parallel foamRun failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

    def test_run_foam_raises_value_error_when_serial_foamrun_fails(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act / Assert
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(1, "error")),
        ):
            with pytest.raises(ValueError, match="foamRun failed"):
                run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestRunFoamEdgeCases:

    def test_run_foam_handles_empty_time_dirs_gracefully(self, tmp_path):
        # Arrange
        case_dir = _make_case_dir(tmp_path)

        # Act
        with (
            patch("module.functions.run_foam.unzip_case", return_value=case_dir),
            patch("module.functions.run_foam.infer_run_config", return_value=_base_config()),
            patch("module.functions.run_foam.validate_case_structure", return_value=[]),
            patch("module.functions.run_foam.run_cmd", return_value=(0, "End\n")),
            patch("module.functions.run_foam.list_time_dirs", return_value=[]),
            patch("module.functions.run_foam.read_control_dict_values", return_value={}),
            patch("module.functions.run_foam.parse_solver_log", return_value=CONVERGENCE_STUB),
            patch("module.functions.run_foam.zip_case",
                  return_value=str(tmp_path / "out.zip")),
        ):
            outputs = run_foam(_input_json(tmp_path / "case.zip"), str(tmp_path))

        # Assert
        report_path = next(o.path for o in outputs if o.name == "convergence_report")
        report = json.loads(Path(report_path).read_text())
        assert report["last_time"] is None
        assert report["fields_at_last_time"] == []
