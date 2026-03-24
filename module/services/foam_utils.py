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
    top_level = [p for p in dest.iterdir() if p.is_dir() and p.name != "__MACOSX"]
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
# Run configuration inference from standard OpenFOAM files
# ---------------------------------------------------------------------------

def infer_run_config(case_dir: Path) -> dict:
    """
    Infer run configuration from standard OpenFOAM files.
    No custom foam_job.json required.

    Returns a dict with keys:
      run_blockmesh       bool  — blockMeshDict present
      run_snappy          bool  — snappyHexMeshDict present
      run_set_fields      bool  — setFieldsDict present
      parallel            bool  — decomposeParDict present and numberOfSubdomains > 1
      np                  int   — numberOfSubdomains (1 if no decomposeParDict)
    """
    config: dict[str, Any] = {}

    config["run_blockmesh"] = (case_dir / "system" / "blockMeshDict").exists()
    config["run_snappy"] = (case_dir / "system" / "snappyHexMeshDict").exists()
    config["run_set_fields"] = (case_dir / "system" / "setFieldsDict").exists()

    decompose_dict = case_dir / "system" / "decomposeParDict"
    if decompose_dict.exists():
        np_val = read_of_value(decompose_dict, "numberOfSubdomains")
        try:
            np_count = int(np_val) if np_val is not None else 1
        except ValueError:
            np_count = 1
        config["parallel"] = np_count > 1
        config["np"] = np_count
    else:
        config["parallel"] = False
        config["np"] = 1

    return config


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
        "application", "solver", "startTime", "endTime", "deltaT",
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


# ---------------------------------------------------------------------------
# Field file parsing (initial conditions)
# ---------------------------------------------------------------------------

def _parse_boundary_field(text: str) -> dict[str, dict[str, str]]:
    """Extract per-patch boundary conditions from an OpenFOAM field file body."""
    m = re.search(r"\bboundaryField\s*\{", text)
    if not m:
        return {}

    # Brace-count to find the end of the boundaryField block.
    start = m.end()
    depth = 1
    pos = start
    while pos < len(text) and depth > 0:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    outer_block = text[start : pos - 1]

    patches: dict[str, dict[str, str]] = {}
    for pm in re.finditer(r"(\w+)\s*\{", outer_block):
        patch_name = pm.group(1)
        inner_start = pm.end()
        inner_depth = 1
        ipos = inner_start
        while ipos < len(outer_block) and inner_depth > 0:
            if outer_block[ipos] == "{":
                inner_depth += 1
            elif outer_block[ipos] == "}":
                inner_depth -= 1
            ipos += 1
        patch_body = outer_block[inner_start : ipos - 1]

        info: dict[str, str] = {}
        tm = re.search(r"^\s*type\s+(\S+)\s*;", patch_body, re.MULTILINE)
        if tm:
            info["type"] = tm.group(1)
        vm = re.search(r"^\s*value\s+(.+?)\s*;", patch_body, re.MULTILINE | re.DOTALL)
        if vm:
            info["value"] = " ".join(vm.group(1).split())
        patches[patch_name] = info

    return patches


def parse_of_field_file(file_path: Path) -> dict[str, Any]:
    """
    Parse an OpenFOAM field file (e.g. 0/U, 0/p).
    Returns dimensions, internal_field string, and per-patch boundary conditions.
    """
    text = file_path.read_text()
    result: dict[str, Any] = {}

    dm = re.search(r"^\s*dimensions\s+(\[[^\]]+\])\s*;", text, re.MULTILINE)
    result["dimensions"] = dm.group(1) if dm else None

    im = re.search(r"^\s*internalField\s+(.+?)(\s*;|\s*\n\s*\d+\s*\n)", text, re.MULTILINE | re.DOTALL)
    if im:
        raw = im.group(1).strip()
        # Truncate nonuniform data to just the type declaration
        result["internal_field"] = raw.split("\n")[0].strip() if "\n" in raw else raw
    else:
        result["internal_field"] = None

    result["boundaries"] = _parse_boundary_field(text)
    return result


def read_initial_conditions(case_dir: Path) -> dict[str, Any]:
    """Parse all field files in the 0/ directory."""
    zero_dir = case_dir / "0"
    if not zero_dir.is_dir():
        return {}
    return {
        f.name: parse_of_field_file(f)
        for f in sorted(zero_dir.iterdir())
        if f.is_file()
    }


def read_physical_properties(case_dir: Path) -> dict[str, Any]:
    """
    Read physical/transport properties from constant/.
    Checks physicalProperties and transportProperties (single-phase),
    then phaseProperties (multiphase VoF).
    """
    result: dict[str, Any] = {}

    # Single-phase: physicalProperties (OF v13) or transportProperties (older)
    for fname in ("physicalProperties", "transportProperties"):
        f = case_dir / "constant" / fname
        if f.exists():
            keys = ["nu", "rho", "viscosityModel", "transportModel"]
            for k in keys:
                v = read_of_value(f, k)
                if v is not None:
                    result[k] = v
            break

    # Multiphase: phaseProperties
    phase_f = case_dir / "constant" / "phaseProperties"
    if phase_f.exists():
        phase_keys = ["phases", "sigma"]
        for k in phase_keys:
            v = read_of_value(phase_f, k)
            if v is not None:
                result[k] = v

    return result


def read_turbulence_properties(case_dir: Path) -> dict[str, Any]:
    """
    Read turbulence model settings from constant/.
    Checks momentumTransport (OF v13) then turbulenceProperties (older).
    """
    for fname in ("momentumTransport", "turbulenceProperties"):
        f = case_dir / "constant" / fname
        if not f.exists():
            continue
        text = f.read_text()
        result: dict[str, Any] = {}
        sim = read_of_value(f, "simulationType")
        if sim:
            result["simulationType"] = sim
        for m in re.finditer(r"\b(RAS|LES)\s*\{([^}]*)\}", text, re.DOTALL):
            model_m = re.search(r"^\s*model\s+(\S+)\s*;", m.group(2), re.MULTILINE)
            if model_m:
                result["model"] = model_m.group(1)
            turb_m = re.search(r"^\s*turbulence\s+(\S+)\s*;", m.group(2), re.MULTILINE)
            if turb_m:
                result["turbulence"] = turb_m.group(1)
        return result
    return {}


# ---------------------------------------------------------------------------
# Field statistics via ofpp
# ---------------------------------------------------------------------------

def compute_field_statistics(
    case_dir: Path, time: str, fields: list[str]
) -> dict[str, Any]:
    """
    Compute min/max/mean statistics for each field at a given time using ofpp.
    Scalar fields → {min, max, mean}.
    Vector fields → {magnitude: {…}, x: {…}, y: {…}, z: {…}}.
    Uniform fields (single value) → {min, max, mean} all equal to that value.
    """
    try:
        import numpy as np
        import Ofpp as ofpp  # type: ignore[import-untyped]
    except ImportError:
        log.warning("Ofpp or numpy not available; skipping field statistics")
        return {}

    stats: dict[str, Any] = {}
    for field_name in fields:
        field_path = case_dir / time / field_name
        if not field_path.is_file():
            continue
        try:
            data = ofpp.parse_internal_field(str(field_path))
            if data is None:
                continue

            arr = np.asarray(data, dtype=float)

            if arr.ndim == 0:
                # uniform scalar
                v = float(arr)
                stats[field_name] = {"min": v, "max": v, "mean": v}
            elif arr.ndim == 1:
                if arr.size == 3:
                    # uniform vector returned as (3,) array
                    mag = float(np.linalg.norm(arr))
                    stats[field_name] = {
                        "magnitude": {"min": mag, "max": mag, "mean": mag},
                        "x": {"min": float(arr[0]), "max": float(arr[0]), "mean": float(arr[0])},
                        "y": {"min": float(arr[1]), "max": float(arr[1]), "mean": float(arr[1])},
                        "z": {"min": float(arr[2]), "max": float(arr[2]), "mean": float(arr[2])},
                    }
                else:
                    # nonuniform scalar field
                    stats[field_name] = {
                        "min": float(np.min(arr)),
                        "max": float(np.max(arr)),
                        "mean": float(np.mean(arr)),
                    }
            elif arr.ndim == 2 and arr.shape[1] == 3:
                # nonuniform vector field
                mag = np.linalg.norm(arr, axis=1)
                stats[field_name] = {
                    "magnitude": {
                        "min": float(np.min(mag)),
                        "max": float(np.max(mag)),
                        "mean": float(np.mean(mag)),
                    },
                    "x": {"min": float(np.min(arr[:, 0])), "max": float(np.max(arr[:, 0])), "mean": float(np.mean(arr[:, 0]))},
                    "y": {"min": float(np.min(arr[:, 1])), "max": float(np.max(arr[:, 1])), "mean": float(np.mean(arr[:, 1]))},
                    "z": {"min": float(np.min(arr[:, 2])), "max": float(np.max(arr[:, 2])), "mean": float(np.mean(arr[:, 2]))},
                }
        except Exception:
            log.warning("Could not compute statistics for field %s at time %s", field_name, time)

    return stats


# ---------------------------------------------------------------------------
# Residual history parsing
# ---------------------------------------------------------------------------

def parse_residual_history(log_text: str) -> dict[str, list[tuple[float, float, float]]]:
    """
    Parse per-iteration initial and final residuals from a solver log.

    Returns {field: [(time_step, initial_residual, final_residual), ...]}
    Captures both residuals per iteration, enabling full convergence curves.
    """
    residuals: dict[str, list] = {}
    current_time: float = 0.0
    time_pat = re.compile(r"^Time = (\S+)$")
    res_pat = re.compile(
        r"Solving for (\w+),\s*Initial residual = ([0-9eE+\-.]+),\s*Final residual = ([0-9eE+\-.]+)"
    )
    for line in log_text.splitlines():
        tm = time_pat.match(line)
        if tm:
            try:
                current_time = float(tm.group(1))
            except ValueError:
                pass
        rm = res_pat.search(line)
        if rm:
            field = rm.group(1)
            init_res = float(rm.group(2))
            final_res = float(rm.group(3))
            residuals.setdefault(field, []).append((current_time, init_res, final_res))
    return residuals


# ---------------------------------------------------------------------------
# Pure-regex field array parsing (no Ofpp required)
# ---------------------------------------------------------------------------

def parse_field_array(file_path: Path) -> tuple:
    """
    Parse the internalField of an OpenFOAM field file into a raw numpy array
    without requiring the Ofpp library.

    Handles:
      - nonuniform List<vector> → np.ndarray shape (n, 3), type 'vector'
      - nonuniform List<scalar> → np.ndarray shape (n,),   type 'scalar'
      - uniform (x y z)         → np.ndarray shape (3,),   type 'vector'
      - uniform value           → np.ndarray shape (1,),   type 'scalar'

    Returns (array, field_type) or (None, None) if parsing fails.
    """
    try:
        import numpy as np
    except ImportError:
        return None, None

    text = file_path.read_text()

    # Nonuniform vector
    m = re.search(
        r"internalField\s+nonuniform\s+List<vector>\s*\n\d+\s*\n\((.*?)\n\)",
        text, re.DOTALL,
    )
    if m:
        vectors = []
        for line in m.group(1).strip().splitlines():
            vm = re.match(
                r"\(\s*([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s*\)",
                line.strip(),
            )
            if vm:
                vectors.append([float(vm.group(1)), float(vm.group(2)), float(vm.group(3))])
        if vectors:
            return np.array(vectors, dtype=float), "vector"

    # Nonuniform scalar
    m = re.search(
        r"internalField\s+nonuniform\s+List<scalar>\s*\n\d+\s*\n\((.*?)\n\)",
        text, re.DOTALL,
    )
    if m:
        scalars = []
        for line in m.group(1).strip().splitlines():
            line = line.strip()
            if line:
                try:
                    scalars.append(float(line))
                except ValueError:
                    pass
        if scalars:
            return np.array(scalars, dtype=float), "scalar"

    # Uniform vector
    m = re.search(
        r"internalField\s+uniform\s+\(\s*([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s+([0-9eE+\-.]+)\s*\)",
        text,
    )
    if m:
        vals = np.array([float(m.group(1)), float(m.group(2)), float(m.group(3))], dtype=float)
        return vals, "vector"

    # Uniform scalar
    m = re.search(r"internalField\s+uniform\s+([0-9eE+\-.]+)", text)
    if m:
        return np.array([float(m.group(1))], dtype=float), "scalar"

    return None, None


# ---------------------------------------------------------------------------
# checkMesh output parsing
# ---------------------------------------------------------------------------

def parse_checkmesh_output(log_text: str) -> dict[str, Any]:
    """
    Parse checkMesh log output for structured mesh quality metrics.

    Returns dict with any of: cells, faces, points,
    max_non_orthogonality, max_skewness, mesh_ok.

    Uses line-start matching to avoid false positives from lines such as
    "internal cells:" or "faces per cell:".
    """
    metrics: dict[str, Any] = {"mesh_ok": False}

    for line in log_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("cells:"):
            m = re.search(r"cells:\s+(\d+)", stripped)
            if m:
                metrics["cells"] = int(m.group(1))
        elif stripped.startswith("faces:"):
            m = re.search(r"faces:\s+(\d+)", stripped)
            if m:
                metrics["faces"] = int(m.group(1))
        elif stripped.startswith("points:"):
            m = re.search(r"points:\s+(\d+)", stripped)
            if m:
                metrics["points"] = int(m.group(1))

        if "non-orthogonality" in line.lower():
            m = re.search(r"non-orthogonality\s+Max:\s*([0-9eE+\-.]+)", line, re.IGNORECASE)
            if m:
                metrics["max_non_orthogonality"] = float(m.group(1))
            m2 = re.search(r"Max non-orthogonality\s*=\s*([0-9eE+\-.]+)", line)
            if m2:
                metrics["max_non_orthogonality"] = float(m2.group(1))

        if "Max skewness" in line:
            m = re.search(r"Max skewness\s*=\s*([0-9eE+\-.]+)", line)
            if m:
                metrics["max_skewness"] = float(m.group(1))

        if "Mesh OK" in line:
            metrics["mesh_ok"] = True

    return metrics


# ---------------------------------------------------------------------------
# blockMeshDict dimension extraction
# ---------------------------------------------------------------------------

def read_blockmesh_dims(case_dir: Path) -> tuple[int, int, int] | None:
    """
    Extract cell counts (nx, ny, nz) from system/blockMeshDict.

    Looks for the first `hex (...) (nx ny nz)` entry.
    Returns (nx, ny, nz) or None if the file is absent or unparseable.
    """
    bmd = case_dir / "system" / "blockMeshDict"
    if not bmd.exists():
        return None
    m = re.search(r"hex\s*\([^)]+\)\s*\((\d+)\s+(\d+)\s+(\d+)\)", bmd.read_text())
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None
