"""
lib/foam_utils.py

Shared utilities for the @your_org:openfoam Istari integration module.
Imported by functions in module/functions/.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FOAM_JOB_FILENAME = "foam_job.json"
REQUIRED_DIRS = {"0", "constant", "system"}
REQUIRED_SYSTEM_FILES = {"controlDict", "fvSchemes", "fvSolution"}


# ---------------------------------------------------------------------------
# I/O helpers — Istari file-based contract
# ---------------------------------------------------------------------------

def read_input(input_file: str) -> dict:
    """Read the Istari-provided input JSON file."""
    with open(input_file) as fh:
        return json.load(fh)


def write_output(output_file: str, payload: dict) -> None:
    """Write the Istari-expected output JSON file."""
    with open(output_file, "w") as fh:
        json.dump(payload, fh, indent=2)
    log.info("Output written to %s", output_file)


# ---------------------------------------------------------------------------
# ZIP / case directory helpers
# ---------------------------------------------------------------------------

def unzip_case(zip_path: str, dest_dir: str) -> Path:
    """
    Unzip a .foam.zip into dest_dir.
    Handles two structures:
      1. Flat: case files at zip root (e.g. system/controlDict at root)
      2. Wrapped: single top-level directory containing the case (e.g. damBreak/system/...)
    Returns the path to the OpenFOAM case root.
    Raises ValueError if the zip structure is unexpected.
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)

    # Check for flat structure first — system/controlDict at root
    if (dest / "system" / "controlDict").exists():
        log.info("Unzipped case to %s (flat structure)", dest)
        return dest

    # Check for wrapped structure — single top-level directory
    top_level = [p for p in dest.iterdir() if p.is_dir()]
    if len(top_level) == 1 and (top_level[0] / "system" / "controlDict").exists():
        case_dir = top_level[0]
        log.info("Unzipped case to %s (wrapped structure)", case_dir)
        return case_dir

    raise ValueError(
        f"Could not locate OpenFOAM case root in zip. "
        f"Expected system/controlDict at root or inside a single top-level directory. "
        f"Contents: {list(dest.iterdir())}"
    )


def zip_case(case_dir: Path, output_zip_path: str) -> str:
    """
    Zip the OpenFOAM case directory back into a .foam.zip.
    Returns the path to the created zip file.
    """
    out = Path(output_zip_path)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in case_dir.rglob("*"):
            arcname = file_path.relative_to(case_dir.parent)
            zf.write(file_path, arcname)
    log.info("Zipped case to %s", out)
    return str(out)


# ---------------------------------------------------------------------------
# foam_job.json
# ---------------------------------------------------------------------------

def read_foam_job(case_dir: Path) -> dict:
    """Read and validate foam_job.json from the case root."""
    job_file = case_dir / FOAM_JOB_FILENAME
    if not job_file.exists():
        raise FileNotFoundError(f"Missing {FOAM_JOB_FILENAME} in {case_dir}")
    with open(job_file) as fh:
        job = json.load(fh)

    required = {"case_name", "foam_version", "solver_module"}
    missing = required - job.keys()
    if missing:
        raise ValueError(f"foam_job.json missing required keys: {missing}")

    job.setdefault("mesh_required", False)
    job.setdefault("parallel", False)
    job.setdefault("np", 1)
    job.setdefault("post_process", [])
    job.setdefault("result_fields", [])
    job.setdefault("tags", [])
    return job


# ---------------------------------------------------------------------------
# Case validation
# ---------------------------------------------------------------------------

def validate_case_structure(case_dir: Path) -> list[str]:
    """
    Check case_dir for required OpenFOAM subdirectories and system files.
    Returns a list of warning/error strings (empty = valid).
    """
    issues = []
    for d in REQUIRED_DIRS:
        if not (case_dir / d).is_dir():
            issues.append(f"Missing required directory: {d}/")

    system_dir = case_dir / "system"
    if system_dir.is_dir():
        for f in REQUIRED_SYSTEM_FILES:
            if not (system_dir / f).exists():
                issues.append(f"Missing system file: system/{f}")

    return issues


# ---------------------------------------------------------------------------
# OpenFOAM dictionary read/write
# ---------------------------------------------------------------------------

def read_of_value(file_path: Path, key: str) -> str | None:
    pattern = re.compile(
        r"^\s*" + re.escape(key) + r"\s+([^;]+?)\s*;",
        re.MULTILINE,
    )
    text = file_path.read_text()
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def write_of_value(file_path: Path, key: str, new_value: str) -> bool:
    pattern = re.compile(
        r"(^\s*" + re.escape(key) + r"\s+)([^;]+?)(\s*;)",
        re.MULTILINE,
    )
    text = file_path.read_text()
    new_text, count = pattern.subn(
        lambda m: m.group(1) + new_value + m.group(3),
        text,
    )
    if count == 0:
        return False
    file_path.write_text(new_text)
    log.info("Patched %s: %s = %s", file_path.name, key, new_value)
    return True


def read_control_dict_values(case_dir: Path) -> dict:
    cd = case_dir / "system" / "controlDict"
    keys = [
        "application", "startTime", "endTime", "deltaT",
        "writeInterval", "startFrom", "stopAt",
    ]
    return {k: read_of_value(cd, k) for k in keys}


# ---------------------------------------------------------------------------
# Shell command runner
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: str | list,
    cwd: Path,
    log_file: Path | None = None,
    env: dict | None = None,
) -> tuple[int, str]:
    full_env = {**os.environ, **(env or {})}
    log.info("Running: %s  (cwd=%s)", cmd, cwd)
    proc = subprocess.Popen(
        cmd,
        shell=isinstance(cmd, str),
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=full_env,
    )
    lines = []
    fh = open(log_file, "w") if log_file else None
    try:
        for line in proc.stdout:
            lines.append(line)
            log.debug(line.rstrip())
            if fh:
                fh.write(line)
    finally:
        if fh:
            fh.close()

    proc.wait()
    output = "".join(lines)
    if proc.returncode != 0:
        log.error("Command failed (rc=%d): %s", proc.returncode, cmd)
    return proc.returncode, output


# ---------------------------------------------------------------------------
# Log / convergence parsing
# ---------------------------------------------------------------------------

def parse_solver_log(log_text: str) -> dict:
    result: dict[str, Any] = {
        "final_residuals": {},
        "time_steps": [],
        "converged": False,
        "execution_time_seconds": None,
        "warnings": [],
        "errors": [],
    }
    res_pattern = re.compile(
        r"Solving for (\w+),.*?Final residual = ([0-9eE+\-.]+)"
    )
    for m in res_pattern.finditer(log_text):
        result["final_residuals"][m.group(1)] = float(m.group(2))

    time_pattern = re.compile(r"^Time = ([0-9eE+\-.]+)$", re.MULTILINE)
    result["time_steps"] = [float(m.group(1)) for m in time_pattern.finditer(log_text)]

    if any(phrase in log_text for phrase in [
        "SIMPLE solution converged", "End", "Finalising parallel run",
    ]):
        result["converged"] = True

    exec_pattern = re.compile(r"ExecutionTime = ([0-9.]+) s")
    exec_matches = exec_pattern.findall(log_text)
    if exec_matches:
        result["execution_time_seconds"] = float(exec_matches[-1])

    result["warnings"] = re.findall(r"--> FOAM Warning.*", log_text)
    result["errors"] = re.findall(r"--> FOAM FATAL.*", log_text)
    return result


# ---------------------------------------------------------------------------
# Time directory utilities
# ---------------------------------------------------------------------------

def list_time_dirs(case_dir: Path) -> list[str]:
    dirs = []
    for p in case_dir.iterdir():
        if p.is_dir():
            try:
                float(p.name)
                dirs.append(p.name)
            except ValueError:
                pass
    return sorted(dirs, key=float)


def list_fields_at_time(case_dir: Path, time: str) -> list[str]:
    time_dir = case_dir / time
    if not time_dir.is_dir():
        return []
    return [f.name for f in time_dir.iterdir() if f.is_file()]
