"""
Integration test for update_foam (formerly patch_foam).

Requires: tests/integration/fixtures/cavity_test.foam.zip
Does NOT require OpenFOAM to be installed.
"""

import json
import sys
import zipfile
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


def _make_input(patches: list, output_case_name: str = "cavity_patched",
                foam_job_patches: dict | None = None) -> str:
    return json.dumps({
        "foam_case": {"type": "user_model", "value": str(FIXTURE)},
        "patches": {"type": "parameter", "value": json.dumps(patches)},
        "foam_job_patches": {"type": "parameter", "value": json.dumps(foam_job_patches or {})},
        "output_case_name": {"type": "parameter", "value": output_case_name},
    })


def test_update_foam_end_time(tmp_path):
    from module.functions.inspect_update_foam import update_foam

    patches = [{"file": "system/controlDict", "key": "endTime", "value": "2.0"}]
    result = update_foam(_make_input(patches), str(tmp_path))

    assert len(result) == 2
    names = {r.name for r in result}
    assert "patched_case" in names
    assert "patch_report" in names


def test_update_foam_report_success(tmp_path):
    from module.functions.inspect_update_foam import update_foam

    patches = [{"file": "system/controlDict", "key": "endTime", "value": "2.0"}]
    result = update_foam(_make_input(patches), str(tmp_path))

    report_out = next(r for r in result if r.name == "patch_report")
    report = json.loads(Path(report_out.path).read_text())

    assert report["patches_applied"] == 1
    assert report["patches_succeeded"] == 1
    assert report["patches_failed"] == 0
    assert report["detail"][0]["success"] is True


def test_update_foam_value_persisted_in_zip(tmp_path):
    """The patched value must actually exist in the output zip."""
    from module.functions.inspect_update_foam import update_foam

    # Add lib/ so we can verify with read_of_value
    _LIB_DIR = str(_PROJECT_ROOT / "lib")
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    from foam_utils import read_of_value

    patches = [{"file": "system/controlDict", "key": "endTime", "value": "2.0"}]
    result = update_foam(_make_input(patches), str(tmp_path))

    case_out = next(r for r in result if r.name == "patched_case")
    zip_path = Path(case_out.path)
    assert zip_path.exists()

    extract_dir = tmp_path / "verify"
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)

    # Find the extracted controlDict
    control_dicts = list(extract_dir.rglob("controlDict"))
    assert len(control_dicts) == 1
    assert read_of_value(control_dicts[0], "endTime") == "2.0"


def test_update_foam_missing_key_reports_failure(tmp_path):
    from module.functions.inspect_update_foam import update_foam

    patches = [{"file": "system/controlDict", "key": "nonExistentKey", "value": "42"}]
    result = update_foam(_make_input(patches), str(tmp_path))

    report_out = next(r for r in result if r.name == "patch_report")
    report = json.loads(Path(report_out.path).read_text())

    assert report["patches_failed"] == 1
    assert report["detail"][0]["success"] is False


def test_update_foam_multiple_patches(tmp_path):
    from module.functions.inspect_update_foam import update_foam

    patches = [
        {"file": "system/controlDict", "key": "endTime", "value": "3.0"},
        {"file": "system/controlDict", "key": "deltaT", "value": "0.01"},
    ]
    result = update_foam(_make_input(patches), str(tmp_path))

    report_out = next(r for r in result if r.name == "patch_report")
    report = json.loads(Path(report_out.path).read_text())

    assert report["patches_applied"] == 2
    assert report["patches_succeeded"] == 2
    assert report["patches_failed"] == 0
