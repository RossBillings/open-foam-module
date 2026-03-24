"""
module/functions/run_foam.py

Istari Integration Function: run_foam
Module: @your_org:openfoam

Full pipeline: unzip → (blockMesh) → (snappyHexMesh) → (setFields)
             → (decomposePar) → foamRun → (reconstructPar)
             → parse log → re-zip solved case.

Registered as "run_foam" in the function registry.
Called by module/__main__.py via get_function("run_foam")(input_json, temp_dir).
"""

import json
import logging
from pathlib import Path
from typing import List

from module.functions.base.function_io import Output, OutputType
from module.functions.registry import register
from module.services.foam_utils import (
    infer_run_config,
    list_fields_at_time,
    list_time_dirs,
    parse_solver_log,
    read_control_dict_values,
    run_cmd,
    unzip_case,
    validate_case_structure,
    write_of_value,
    zip_case,
)

log = logging.getLogger(__name__)


def run_foam(input_json: str, temp_dir: str) -> List[Output]:
    """
    Full OpenFOAM pipeline: unzip → mesh → solve → re-zip.

    :param input_json: JSON string with Istari input envelope.
    :param temp_dir: Scratch directory provided by Istari agent.
    :return: List of Output objects (solved_case, run_log, convergence_report).
    """
    raw = json.loads(input_json)

    # Extract values from Istari input envelope
    zip_path = raw["foam_case"]["value"]
    override_end_time = raw["override_end_time"]["value"] if "override_end_time" in raw else None
    override_np = raw["override_np"]["value"] if "override_np" in raw else None

    temp = Path(temp_dir)
    log_dir = temp / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log.info("=== run_foam START ===")

    # 1. Unzip
    case_dir = unzip_case(zip_path, str(temp / "case"))
    case_name = case_dir.name

    # 2. Infer run config from standard OpenFOAM files
    config = infer_run_config(case_dir)
    log.info("Inferred run config: %s", json.dumps(config, indent=2))

    # 3. Validate structure
    issues = validate_case_structure(case_dir)
    if issues:
        raise ValueError("Case validation failed:\n" + "\n".join(issues))

    # 4. Apply input overrides
    cd_path = case_dir / "system" / "controlDict"
    if override_end_time is not None:
        write_of_value(cd_path, "endTime", str(override_end_time))
    if override_np is not None:
        np_count = int(override_np)
        config["np"] = np_count
        dp = case_dir / "system" / "decomposeParDict"
        if dp.exists():
            write_of_value(dp, "numberOfSubdomains", str(np_count))
        if np_count > 1:
            config["parallel"] = True

    # 5. Pre-processing
    poly_mesh = case_dir / "constant" / "polyMesh"
    mesh_exists = poly_mesh.is_dir() and any(poly_mesh.iterdir())

    if config["run_blockmesh"] and not mesh_exists:
        rc, _ = run_cmd("blockMesh", cwd=case_dir, log_file=log_dir / "blockMesh.log")
        if rc != 0:
            raise ValueError(f"blockMesh failed (rc={rc})")

    if config["run_snappy"]:
        rc, _ = run_cmd("snappyHexMesh -overwrite", cwd=case_dir,
                        log_file=log_dir / "snappyHexMesh.log")
        if rc != 0:
            raise ValueError(f"snappyHexMesh failed (rc={rc})")

    if config["run_set_fields"]:
        rc, _ = run_cmd("setFields", cwd=case_dir, log_file=log_dir / "setFields.log")
        if rc != 0:
            raise ValueError(f"setFields failed (rc={rc})")

    # 6. Solve
    solver_log = log_dir / "foamRun.log"
    parallel = config["parallel"]
    np_count = config["np"]

    if parallel and np_count > 1:
        rc, _ = run_cmd("decomposePar", cwd=case_dir, log_file=log_dir / "decomposePar.log")
        if rc != 0:
            raise ValueError(f"decomposePar failed (rc={rc})")
        rc, _ = run_cmd(
            f"mpirun -np {np_count} foamRun -parallel",
            cwd=case_dir,
            log_file=solver_log,
        )
        if rc != 0:
            raise ValueError(f"Parallel foamRun failed (rc={rc})")
        rc, _ = run_cmd("reconstructPar", cwd=case_dir, log_file=log_dir / "reconstructPar.log")
        if rc != 0:
            log.warning("reconstructPar failed (rc=%d)", rc)
    else:
        rc, _ = run_cmd("foamRun", cwd=case_dir, log_file=solver_log)
        if rc != 0:
            raise ValueError(f"foamRun failed (rc={rc})")

    # 7. Create ParaView touch file (<case_name>.foam) in case root
    foam_touch = case_dir / f"{case_name}.foam"
    foam_touch.touch()
    log.info("Created ParaView touch file: %s", foam_touch.name)

    # 8. Convergence report
    log_text = solver_log.read_text() if solver_log.exists() else ""
    convergence = parse_solver_log(log_text)
    time_dirs = list_time_dirs(case_dir)
    last_time = time_dirs[-1] if time_dirs else None
    report = {
        "case_name": case_name,
        "control_dict": read_control_dict_values(case_dir),
        "time_dirs_written": time_dirs,
        "last_time": last_time,
        "fields_at_last_time": list_fields_at_time(case_dir, last_time) if last_time else [],
        **convergence,
    }
    convergence_path = temp / "convergence_report.json"
    convergence_path.write_text(json.dumps(report, indent=2))

    # 9. Copy logs into case archive + solver log to case root for extract_foam
    case_logs_dir = case_dir / "logs"
    case_logs_dir.mkdir(exist_ok=True)
    for lf in log_dir.iterdir():
        (case_logs_dir / lf.name).write_bytes(lf.read_bytes())
    # foamRun.log at case root so extract_foam can parse residuals/convergence
    if solver_log.exists():
        (case_dir / "foamRun.log").write_bytes(solver_log.read_bytes())

    # 10. Re-zip solved case
    solved_zip_name = f"{case_name}_solved.foam.zip"
    solved_zip_path = zip_case(case_dir, str(temp / solved_zip_name))

    log.info("=== run_foam COMPLETE — converged=%s ===", report["converged"])

    return [
        Output(name="solved_case", type=OutputType.FILE, path=str(Path(solved_zip_path).resolve())),
        Output(name="run_log", type=OutputType.FILE, path=str(solver_log.resolve())),
        Output(name="convergence_report", type=OutputType.FILE, path=str(convergence_path.resolve())),
    ]


register("run_foam", run_foam)
