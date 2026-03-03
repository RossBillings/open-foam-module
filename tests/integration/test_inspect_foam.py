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

    assert len(result) == 1
    assert result[0].name == "inspection_report"
    report_path = Path(result[0].path)
    assert report_path.exists()

    report = json.loads(report_path.read_text())
    assert report["structure_valid"] is True
    assert report["structure_issues"] == []


def test_inspect_foam_job_fields(tmp_path):
    from module.functions.inspect_patch_foam import inspect_foam

    result = inspect_foam(_make_input(tmp_path), str(tmp_path))
    report = json.loads(Path(result[0].path).read_text())

    job = report["foam_job"]
    assert job["case_name"] == "cavity_test"
    assert job["foam_version"] == "13"
    assert job["solver_module"] == "incompressibleFluid"


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
