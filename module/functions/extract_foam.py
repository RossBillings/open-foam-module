"""
module/functions/extract_foam.py

Istari Integration Function: extract_foam

Extracts structured JSON data from an OpenFOAM case (solved or unsolved):
  - inputs  : simulation configuration, initial conditions, physical/turbulence properties
  - outputs : time directories, field statistics (via ofpp), and convergence data
               (only populated when the case has been solved)

Registered name: "extract_foam"
Called by module/__main__.py via get_function(name)(input_json, temp_dir).
"""

import json
import logging
from pathlib import Path
from typing import Any, List

from module.functions.base.function_io import Output, OutputType
from module.functions.registry import register
from module.services.foam_utils import (
    compute_field_statistics,
    infer_run_config,
    list_fields_at_time,
    list_time_dirs,
    parse_solver_log,
    read_control_dict_values,
    read_initial_conditions,
    read_physical_properties,
    read_turbulence_properties,
    unzip_case,
)

log = logging.getLogger(__name__)


def extract_foam(input_json: str, temp_dir: str) -> List[Output]:
    """
    Extract structured input/output data from an OpenFOAM case zip.

    Input JSON:
        foam_case  (user_model)  — path to .foam.zip

    Outputs:
        extraction_report  (FILE)  — JSON report with inputs and (if solved) outputs sections
    """
    raw = json.loads(input_json)
    zip_path = raw["foam_case"]["value"]

    temp = Path(temp_dir)
    temp.mkdir(parents=True, exist_ok=True)

    log.info("=== extract_foam START ===")

    case_dir = unzip_case(zip_path, str(temp / "case"))

    report: dict[str, Any] = {
        "case_name": case_dir.name,
        "solved": False,
        "inputs": _extract_inputs(case_dir),
        "outputs": None,
    }

    time_dirs = list_time_dirs(case_dir)
    solved = len(time_dirs) > 1
    report["solved"] = solved

    if solved:
        report["outputs"] = _extract_outputs(case_dir, time_dirs)

    report_path = temp / "extraction_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    log.info("=== extract_foam COMPLETE — solved=%s ===", solved)

    return [
        Output(
            name="extraction_report",
            type=OutputType.FILE,
            path=str(report_path.resolve()),
        )
    ]


def _extract_inputs(case_dir: Path) -> dict[str, Any]:
    cd = read_control_dict_values(case_dir)
    run_config = infer_run_config(case_dir)

    return {
        "solver": cd.get("solver") or cd.get("application"),
        "time_control": {
            "start_time": _to_number(cd.get("startTime")),
            "end_time": _to_number(cd.get("endTime")),
            "delta_t": _to_number(cd.get("deltaT")),
            "write_interval": _to_number(cd.get("writeInterval")),
            "start_from": cd.get("startFrom"),
            "stop_at": cd.get("stopAt"),
        },
        "parallel": {
            "enabled": run_config["parallel"],
            "n_processors": run_config["np"],
            "decompose_method": _read_decompose_method(case_dir),
        },
        "preprocessing": {
            "blockMesh": run_config["run_blockmesh"],
            "snappyHexMesh": run_config["run_snappy"],
            "setFields": run_config["run_set_fields"],
        },
        "initial_conditions": read_initial_conditions(case_dir),
        "physical_properties": read_physical_properties(case_dir),
        "turbulence": read_turbulence_properties(case_dir),
    }


def _extract_outputs(case_dir: Path, time_dirs: list[str]) -> dict[str, Any]:
    final_time = time_dirs[-1]
    fields = list_fields_at_time(case_dir, final_time)

    convergence: dict[str, Any] = {}
    log_path = case_dir / "foamRun.log"
    if log_path.exists():
        convergence = parse_solver_log(log_path.read_text())
    else:
        log.info("foamRun.log not found; convergence data will be empty")

    return {
        "time_directories": time_dirs,
        "final_time": final_time,
        "fields_at_final_time": fields,
        "convergence": convergence,
        "field_statistics": compute_field_statistics(case_dir, final_time, fields),
    }


def _read_decompose_method(case_dir: Path) -> str | None:
    from module.services.foam_utils import read_of_value
    f = case_dir / "system" / "decomposeParDict"
    return read_of_value(f, "method") if f.exists() else None


def _to_number(value: str | None) -> float | int | str | None:
    """Convert a string value to int or float if possible, otherwise return as-is."""
    if value is None:
        return None
    try:
        f = float(value)
        return int(f) if f == int(f) else f
    except (ValueError, OverflowError):
        return value


register("extract_foam", extract_foam)
