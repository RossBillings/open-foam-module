"""
module/functions/inspect_patch_foam.py

Two Istari Integration Functions:
  - inspect_foam  : Pre-flight case validation and reporting
  - update_foam   : Modify OF parameters and return new .foam.zip

Both registered in the function registry.
Called by module/__main__.py via get_function(name)(input_json, temp_dir).
"""

import json
import logging
from pathlib import Path
from typing import List

from module.functions.base.function_io import Output, OutputType
from module.functions.registry import register
from module.services.foam_utils import (
    extract_inputs,
    infer_run_config,
    list_time_dirs,
    read_control_dict_values,
    run_cmd,
    unzip_case,
    validate_case_structure,
    write_of_value,
    zip_case,
)

log = logging.getLogger(__name__)


# =============================================================================
# inspect_foam
# =============================================================================

def inspect_foam(input_json: str, temp_dir: str) -> List[Output]:
    """
    Lightweight pre-flight: validate case structure, report controlDict
    settings, and optionally run checkMesh.

    :param input_json: JSON string with Istari input envelope.
    :param temp_dir: Scratch directory provided by Istari agent.
    :return: List containing a single Output pointing to the inspection report JSON.
    """
    raw = json.loads(input_json)

    zip_path = raw["foam_case"]["value"]
    run_checkmesh = bool(raw["run_checkmesh"]["value"]) if "run_checkmesh" in raw else False

    temp = Path(temp_dir)
    log_dir = temp / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log.info("=== inspect_foam START ===")

    case_dir = unzip_case(zip_path, str(temp / "case"))
    report: dict = {}

    # Structure
    issues = validate_case_structure(case_dir)
    report["structure_issues"] = issues
    report["structure_valid"] = len(issues) == 0

    # controlDict
    report["control_dict"] = read_control_dict_values(case_dir)

    # Inferred run config (pre-processing steps detected)
    run_config = infer_run_config(case_dir)
    pre_steps = []
    if run_config["run_blockmesh"]:
        pre_steps.append("blockMesh")
    if run_config["run_snappy"]:
        pre_steps.append("snappyHexMesh")
    if run_config["run_set_fields"]:
        pre_steps.append("setFields")
    report["pre_processing_detected"] = pre_steps
    report["parallel_detected"] = run_config["parallel"]
    report["np_detected"] = run_config["np"]

    # Mesh status
    poly_mesh = case_dir / "constant" / "polyMesh"
    report["mesh_present"] = poly_mesh.is_dir() and any(poly_mesh.iterdir())
    report["blockmeshdict_present"] = (case_dir / "system" / "blockMeshDict").exists()
    report["decompose_par_dict_present"] = (case_dir / "system" / "decomposeParDict").exists()

    # Fields in 0/
    zero_dir = case_dir / "0"
    report["initial_fields"] = (
        [f.name for f in zero_dir.iterdir() if f.is_file()]
        if zero_dir.is_dir() else []
    )

    # Existing time directories
    time_dirs = list_time_dirs(case_dir)
    report["time_dirs_present"] = time_dirs
    report["already_solved"] = len(time_dirs) > 1

    # checkMesh (optional)
    if run_checkmesh and report["mesh_present"]:
        rc, output = run_cmd(
            "checkMesh", cwd=case_dir, log_file=log_dir / "checkMesh.log"
        )
        report["checkmesh_returncode"] = rc
        report["checkmesh_summary"] = [
            line.strip() for line in output.splitlines()
            if any(kw in line for kw in [
                "cells:", "faces:", "points:", "Max skewness",
                "Max aspect ratio", "Mesh OK", "FAILED",
            ])
        ]
    elif run_checkmesh:
        report["checkmesh_summary"] = ["Skipped — no mesh present"]

    report_path = temp / "inspection_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    # --- inputs.json ---
    outputs = [
        Output(name="inspection_report", type=OutputType.FILE, path=str(report_path.resolve())),
    ]
    try:
        pre_steps = []
        if run_config["run_blockmesh"]:
            pre_steps.append("blockMesh")
        if run_config["run_snappy"]:
            pre_steps.append("snappyHexMesh")
        if run_config["run_set_fields"]:
            pre_steps.append("setFields")
        job = {
            "case_name": case_dir.name,
            "solver_module": None,
            "parallel": run_config.get("parallel", False),
            "np": run_config.get("np", 1),
            "preprocess": pre_steps,
            "foam_version": "13",
        }
        inputs_data = extract_inputs(str(case_dir), job, Path(zip_path).name)
        inputs_path = temp / "inputs.json"
        inputs_path.write_text(json.dumps(inputs_data, indent=2))
        log.info(
            "inputs.json: endTime=%s deltaT=%s application=%s",
            inputs_data["time"].get("endTime"),
            inputs_data["time"].get("deltaT"),
            inputs_data["solver"].get("application"),
        )
        outputs.append(Output(name="inputs", type=OutputType.FILE, path=str(inputs_path.resolve())))
    except Exception as e:
        log.warning("extract_inputs failed, omitting inputs output: %s", e)

    log.info("=== inspect_foam COMPLETE — structure_valid=%s ===", report["structure_valid"])

    return outputs


register("inspect_foam", inspect_foam)


# =============================================================================
# update_foam
# =============================================================================

def update_foam(input_json: str, temp_dir: str) -> List[Output]:
    """
    Apply parameter patches to an OpenFOAM case and return a new .foam.zip.
    Does not run the solver.

    :param input_json: JSON string with Istari input envelope.
    :param temp_dir: Scratch directory provided by Istari agent.
    :return: List containing patched_case and patch_report outputs.
    """
    raw = json.loads(input_json)

    zip_path = raw["foam_case"]["value"]

    # input_json may be passed as a JSON string
    patches_raw = raw["input_json"]["value"] if "input_json" in raw else None
    if isinstance(patches_raw, str):
        patches = json.loads(patches_raw) if patches_raw else []
    else:
        patches = patches_raw or []

    output_case_name = raw["output_case_name"]["value"] if "output_case_name" in raw else None

    temp = Path(temp_dir)
    temp.mkdir(parents=True, exist_ok=True)

    log.info("=== update_foam START === (%d patches)", len(patches))

    case_dir = unzip_case(zip_path, str(temp / "case"))

    # Apply OF dict patches
    patch_report = []
    for patch in patches:
        file_rel = patch.get("file")
        key = patch.get("key")
        value = patch.get("value")

        if not all([file_rel, key, value is not None]):
            patch_report.append({**patch, "success": False, "reason": "Incomplete patch spec"})
            continue

        target = case_dir / file_rel
        if not target.exists():
            patch_report.append({**patch, "success": False, "reason": f"File not found: {file_rel}"})
            continue

        ok = write_of_value(target, key, str(value))
        patch_report.append({
            **patch,
            "success": ok,
            "reason": "OK" if ok else f"Key '{key}' not found in {file_rel}",
        })

    # Optional rename
    if output_case_name:
        new_case_dir = case_dir.parent / output_case_name
        case_dir.rename(new_case_dir)
        case_dir = new_case_dir

    # Re-zip
    zip_name = f"{output_case_name or case_dir.name + '_patched'}.foam.zip"
    patched_zip = zip_case(case_dir, str(temp / zip_name))

    failed = [p for p in patch_report if not p["success"]]
    full_report = {
        "patches_applied": len(patches),
        "patches_succeeded": len(patches) - len(failed),
        "patches_failed": len(failed),
        "detail": patch_report,
    }
    report_path = temp / "patch_report.json"
    report_path.write_text(json.dumps(full_report, indent=2))

    log.info("=== update_foam COMPLETE === (%d failed)", len(failed))

    return [
        Output(name="patched_case", type=OutputType.FILE, path=str(Path(patched_zip).resolve())),
        Output(name="patch_report", type=OutputType.FILE, path=str(report_path.resolve())),
    ]


register("update_foam", update_foam)
