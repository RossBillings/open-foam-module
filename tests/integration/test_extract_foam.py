"""
Integration tests for extract_foam.

Uses tests/integration/fixtures/cavity_test.foam.zip (unsolved case).
Does NOT require OpenFOAM to be installed.
"""

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

FIXTURE = _PROJECT_ROOT / "tests" / "integration" / "fixtures" / "cavity_test.foam.zip"


@pytest.fixture(autouse=True)
def require_fixture():
    if not FIXTURE.exists():
        pytest.skip(f"Integration fixture not found: {FIXTURE}")


def _make_input(tmp_path: Path) -> str:
    return json.dumps({
        "foam_case": {"type": "user_model", "value": str(FIXTURE)},
    })


def _load_report(tmp_path: Path) -> dict:
    from module.functions.extract_foam import extract_foam
    result = extract_foam(_make_input(tmp_path), str(tmp_path))
    assert len(result) == 1
    assert result[0].name == "extraction_report"
    return json.loads(Path(result[0].path).read_text())


def test_extract_foam_returns_single_output(tmp_path):
    from module.functions.extract_foam import extract_foam
    result = extract_foam(_make_input(tmp_path), str(tmp_path))
    assert len(result) == 1
    assert result[0].name == "extraction_report"
    assert Path(result[0].path).exists()


def test_extract_foam_unsolved_case(tmp_path):
    report = _load_report(tmp_path)
    assert report["solved"] is False
    assert report["outputs"] is None


def test_extract_foam_case_name(tmp_path):
    report = _load_report(tmp_path)
    assert report["case_name"] == "cavity_test"


def test_extract_foam_inputs_present(tmp_path):
    report = _load_report(tmp_path)
    assert "inputs" in report
    inputs = report["inputs"]
    assert "time_control" in inputs
    assert "parallel" in inputs
    assert "preprocessing" in inputs
    assert "initial_conditions" in inputs
    assert "physical_properties" in inputs
    assert "turbulence" in inputs


def test_extract_foam_time_control(tmp_path):
    report = _load_report(tmp_path)
    tc = report["inputs"]["time_control"]
    assert tc["end_time"] == 10
    assert tc["delta_t"] == pytest.approx(0.005)
    assert tc["start_from"] == "startTime"


def test_extract_foam_preprocessing(tmp_path):
    report = _load_report(tmp_path)
    pre = report["inputs"]["preprocessing"]
    assert pre["blockMesh"] is True
    assert pre["snappyHexMesh"] is False
    assert pre["setFields"] is False


def test_extract_foam_parallel(tmp_path):
    report = _load_report(tmp_path)
    par = report["inputs"]["parallel"]
    assert par["enabled"] is False
    assert par["n_processors"] == 1


def test_extract_foam_initial_conditions_fields(tmp_path):
    report = _load_report(tmp_path)
    ic = report["inputs"]["initial_conditions"]
    assert "U" in ic
    assert "p" in ic


def test_extract_foam_initial_conditions_structure(tmp_path):
    report = _load_report(tmp_path)
    u_field = report["inputs"]["initial_conditions"]["U"]
    assert u_field["dimensions"] == "[0 1 -1 0 0 0 0]"
    assert u_field["internal_field"] == "uniform (0 0 0)"
    assert "boundaries" in u_field


def test_extract_foam_initial_conditions_boundaries(tmp_path):
    report = _load_report(tmp_path)
    boundaries = report["inputs"]["initial_conditions"]["U"]["boundaries"]
    assert "movingWall" in boundaries
    assert boundaries["movingWall"]["type"] == "fixedValue"
    assert "fixedWalls" in boundaries


def test_extract_foam_physical_properties(tmp_path):
    report = _load_report(tmp_path)
    props = report["inputs"]["physical_properties"]
    assert "nu" in props


def test_extract_foam_turbulence(tmp_path):
    report = _load_report(tmp_path)
    turb = report["inputs"]["turbulence"]
    assert "simulationType" in turb
    assert turb["simulationType"] == "RAS"
    assert turb.get("model") == "kEpsilon"
