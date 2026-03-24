"""
module/functions/extract_foam.py

Istari Integration Function: extract_foam

Extracts structured data from an OpenFOAM case (solved or unsolved).

Artifacts produced:
  Always:
    extraction_report.json   — full structured report (inputs + outputs sections)

  When solved:
    residual_history.csv     — per-iteration initial & final residuals (tabular)
    convergence_plot.png     — semilogy convergence history chart
    field_statistics.csv     — min/max/mean per field and component (tabular)
    {field}_contour.png      — 2-D filled contour per field (when mesh dims available)

Registered name: "extract_foam"
Called by module/__main__.py via get_function(name)(input_json, temp_dir).
"""

import csv
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
    parse_field_array,
    parse_residual_history,
    parse_solver_log,
    read_blockmesh_dims,
    read_control_dict_values,
    read_initial_conditions,
    read_physical_properties,
    read_turbulence_properties,
    unzip_case,
)
from module.services.foam_viz import plot_convergence, plot_field_contour

log = logging.getLogger(__name__)


def extract_foam(input_json: str, temp_dir: str) -> List[Output]:
    """
    Extract structured input/output data from an OpenFOAM case zip.

    Input JSON:
        foam_case  (user_model)  — path to .foam.zip

    Outputs:
        extraction_report  (JSON)  — always present
        residual_history   (CSV)   — per-iteration residuals, if solved
        convergence_plot   (PNG)   — semilogy convergence chart, if solved
        field_statistics   (CSV)   — field min/max/mean, if solved
        {field}_contour    (PNG)   — 2-D field contours, if solved + mesh dims known
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

    artifacts: List[Output] = []

    if solved:
        outputs_data, solved_artifacts = _extract_outputs(case_dir, time_dirs, temp)
        report["outputs"] = outputs_data
        artifacts.extend(solved_artifacts)

    report_path = temp / "extraction_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    log.info("=== extract_foam COMPLETE — solved=%s ===", solved)

    return [
        Output(
            name="extraction_report",
            type=OutputType.FILE,
            path=str(report_path.resolve()),
        ),
        *artifacts,
    ]


# ---------------------------------------------------------------------------
# Inputs extraction
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Outputs extraction (solved cases only)
# ---------------------------------------------------------------------------

def _extract_outputs(
    case_dir: Path,
    time_dirs: list[str],
    temp: Path,
) -> tuple[dict[str, Any], List[Output]]:
    """Extract solved-case data and generate CSV/PNG artifacts."""
    final_time = time_dirs[-1]
    fields = list_fields_at_time(case_dir, final_time)

    # Convergence + residual history
    convergence: dict[str, Any] = {}
    residual_history: dict[str, list] = {}
    log_path = case_dir / "foamRun.log"
    if log_path.exists():
        log_text = log_path.read_text()
        convergence = parse_solver_log(log_text)
        residual_history = parse_residual_history(log_text)
    else:
        log.info("foamRun.log not found; convergence data will be empty")

    # Field statistics
    field_stats = compute_field_statistics(case_dir, final_time, fields)

    outputs_data: dict[str, Any] = {
        "time_directories": time_dirs,
        "final_time": final_time,
        "fields_at_final_time": fields,
        "convergence": convergence,
        "residual_history": residual_history,
        "field_statistics": field_stats,
    }

    artifacts: List[Output] = []

    # residual_history.csv + convergence_plot.png
    if residual_history:
        csv_path = temp / "residual_history.csv"
        _write_residual_csv(residual_history, csv_path)
        artifacts.append(Output(
            name="residual_history",
            type=OutputType.FILE,
            path=str(csv_path.resolve()),
        ))

        png_path = temp / "convergence_plot.png"
        if plot_convergence(residual_history, str(png_path)):
            artifacts.append(Output(
                name="convergence_plot",
                type=OutputType.FILE,
                path=str(png_path.resolve()),
            ))

    # field_statistics.csv
    if field_stats:
        stats_csv = temp / "field_statistics.csv"
        _write_field_stats_csv(field_stats, stats_csv)
        artifacts.append(Output(
            name="field_statistics",
            type=OutputType.FILE,
            path=str(stats_csv.resolve()),
        ))

    # {field}_contour.png — one per field when mesh dims are available
    mesh_dims = read_blockmesh_dims(case_dir)
    if mesh_dims:
        nx, ny, _ = mesh_dims
        for field_name in fields:
            field_path = case_dir / final_time / field_name
            if not field_path.is_file():
                continue
            arr, _ = parse_field_array(field_path)
            if arr is None:
                continue
            png_path = temp / f"{field_name}_contour.png"
            if plot_field_contour(arr, (nx, ny), field_name, str(png_path)):
                artifacts.append(Output(
                    name=f"{field_name}_contour",
                    type=OutputType.FILE,
                    path=str(png_path.resolve()),
                ))

    return outputs_data, artifacts


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def _write_residual_csv(
    residual_history: dict[str, list[tuple[float, float, float]]],
    path: Path,
) -> None:
    """CSV columns: time_step, field, initial_residual, final_residual."""
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["time_step", "field", "initial_residual", "final_residual"])
        for field, data in residual_history.items():
            for time_step, init_res, final_res in data:
                writer.writerow([time_step, field, init_res, final_res])


def _write_field_stats_csv(field_stats: dict[str, Any], path: Path) -> None:
    """CSV columns: field, component, min, max, mean.
    Scalar fields use component='scalar'; vector fields emit magnitude + x/y/z rows.
    """
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["field", "component", "min", "max", "mean"])
        for field, stats in field_stats.items():
            if "min" in stats:
                # Scalar
                writer.writerow([field, "scalar", stats["min"], stats["max"], stats["mean"]])
            else:
                # Vector — magnitude + components
                for component in ("magnitude", "x", "y", "z"):
                    if component in stats:
                        s = stats[component]
                        writer.writerow([field, component, s["min"], s["max"], s["mean"]])


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

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
