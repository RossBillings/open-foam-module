"""
Integration test for run_foam.

Requires:
  - tests/integration/fixtures/cavity_test.foam.zip
  - OpenFOAM v13 installed and sourced (blockMesh, foamRun on PATH)
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

FIXTURE = _PROJECT_ROOT / "tests" / "integration" / "fixtures" / "cavity_test.foam.zip"

openfoam_available = shutil.which("blockMesh") is not None and shutil.which("foamRun") is not None


@pytest.fixture(autouse=True)
def require_fixture_and_foam():
    if not FIXTURE.exists():
        pytest.skip(f"Integration fixture not found: {FIXTURE}")
    if not openfoam_available:
        pytest.skip("OpenFOAM not available (blockMesh/foamRun not on PATH)")


def _make_input(override_end_time: float = 0.05, override_np: int = 1) -> str:
    return json.dumps({
        "foam_case": {"type": "user_model", "value": str(FIXTURE)},
        "override_end_time": {"type": "parameter", "value": override_end_time},
        "override_np": {"type": "parameter", "value": override_np},
    })


def test_run_foam_outputs_exist(tmp_path):
    from module.functions.run_foam import run_foam

    result = run_foam(_make_input(), str(tmp_path))

    names = {r.name for r in result}
    assert "solved_case" in names
    assert "run_log" in names

    for r in result:
        assert Path(r.path).exists(), f"Output missing: {r.name} at {r.path}"


def test_run_foam_converged(tmp_path):
    from module.functions.run_foam import run_foam

    result = run_foam(_make_input(), str(tmp_path))

    convergence_out = next((r for r in result if r.name == "convergence_report"), None)
    assert convergence_out is not None, "convergence_report output not produced"

    report = json.loads(Path(convergence_out.path).read_text())
    assert report["converged"] is True


def test_run_foam_end_time_override(tmp_path):
    """override_end_time should be reflected in convergence report."""
    from module.functions.run_foam import run_foam

    result = run_foam(_make_input(override_end_time=0.05), str(tmp_path))

    convergence_out = next(r for r in result if r.name == "convergence_report")
    report = json.loads(Path(convergence_out.path).read_text())

    assert report["control_dict"]["endTime"] == "0.05"


def test_run_foam_result_fields_present(tmp_path):
    """Fields declared in foam_job result_fields should appear in last time dir."""
    from module.functions.run_foam import run_foam

    result = run_foam(_make_input(), str(tmp_path))

    convergence_out = next(r for r in result if r.name == "convergence_report")
    report = json.loads(Path(convergence_out.path).read_text())

    fields = report.get("fields_at_last_time", [])
    assert "U" in fields
    assert "p" in fields
