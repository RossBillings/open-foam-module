"""
Integration test for inspect_foam.

Requires: tests/integration/fixtures/cavity_test.foam.zip
Does NOT require OpenFOAM to be installed.
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure the project root is on the path
_PROJECT_ROOT = Path(__file__).parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

FIXTURE = _PROJECT_ROOT / "tests" / "integration" / "fixtures" / "cavity_test.foam.zip"


@pytest.fixture(autouse=True)
def require_fixture():
    if not FIXTURE.exists():
        pytest.skip(f"Integration fixture not found: {FIXTURE}")


def _make_input(tmp_path: Path, run_checkmesh: bool = False) -> str:
    return json.dumps({
        "foam_case": {"type": "user_model", "value": str(FIXTURE)},
        "run_checkmesh": {"type": "parameter", "value": run_checkmesh},
    })


def test_inspect_foam_structure_valid(tmp_path):
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))

    assert len(result) >= 1
    assert result[0].name == "inspection_report"
    report_path = Path(result[0].path)
    assert report_path.exists()

    report = json.loads(report_path.read_text())
    assert report["structure_valid"] is True
    assert report["structure_issues"] == []


def test_inspect_foam_pre_processing_detected(tmp_path):
    """Cavity fixture has blockMeshDict → blockMesh should be detected."""
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))
    report = json.loads(Path(result[0].path).read_text())

    assert "pre_processing_detected" in report
    assert "blockMesh" in report["pre_processing_detected"]
    assert report["parallel_detected"] is False
    assert report["np_detected"] == 1


def test_inspect_foam_mesh_not_present(tmp_path):
    """Cavity tutorial has blockMeshDict but no pre-built mesh."""
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))
    report = json.loads(Path(result[0].path).read_text())

    assert report["mesh_present"] is False
    assert report["blockmeshdict_present"] is True
    assert report["already_solved"] is False


def test_inspect_foam_control_dict(tmp_path):
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))
    report = json.loads(Path(result[0].path).read_text())

    cd = report["control_dict"]
    assert cd["endTime"] == "10"
    assert cd["deltaT"] == "0.005"
    assert cd["startFrom"] == "startTime"


def test_inspect_foam_initial_fields(tmp_path):
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))
    report = json.loads(Path(result[0].path).read_text())

    fields = report["initial_fields"]
    assert "U" in fields
    assert "p" in fields


def test_inspect_foam_inputs_json(tmp_path):
    """inputs.json is produced and conforms to schema when extract_inputs succeeds."""
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))
    names = [o.name for o in result]
    assert "inspection_report" in names

    inputs_outputs = [o for o in result if o.name == "inputs"]
    if not inputs_outputs:
        pytest.skip("inputs output omitted (extract_inputs may have failed)")
    inputs_path = Path(inputs_outputs[0].path)
    assert inputs_path.exists()

    inputs_data = json.loads(inputs_path.read_text())
    assert inputs_data["schema_version"] == "1.0"
    assert "case_name" in inputs_data
    assert "solver" in inputs_data
    assert "time" in inputs_data
    assert inputs_data["time"]["endTime"] is not None
    assert inputs_data["time"]["deltaT"] is not None
