"""
OpenFOAM: 1 input (case) + parameters → multiple outputs (ModelParamsToArtifactsNoAuth)

Takes ONE case input (archive or directory) plus PARAMETERS, produces MULTIPLE output files.
No authentication required.

Input: case (user_model) - .tgz/.tar.gz archive or case directory
Parameters: n_processors, include_summary, output_format
Outputs: summary, results, log
"""

import logging
import tarfile
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Extra, Field, ValidationError

from module.functions.base.function_io import Input, Output, OutputType
from module.functions.registry import register

logger = logging.getLogger(__name__)


# ============================================================================
# OPENFOAM BUSINESS LOGIC - IMPLEMENT foamRun, blockMesh, etc.
# ============================================================================


def process_openfoam_case(
    case_path: Path,
    output_dir: Path,
    n_processors: int,
    include_summary: bool,
    output_format: str,
) -> List[tuple[str, Path]]:
    """
    Process an OpenFOAM case and produce output artifacts.

    TODO: Implement actual OpenFOAM workflow:
    - Source OpenFOAM environment
    - Run blockMesh, foamRun (or decomposePar + mpirun foamRun -parallel + reconstructPar)
    - Export results (foamToVTK, etc.)
    - Parse logs for summary

    Args:
        case_path: Path to extracted case directory
        output_dir: Directory where output artifacts should be written
        n_processors: Number of MPI processes (1 = serial)
        include_summary: Whether to generate a summary file
        output_format: Output format for results (vtk, csv, etc.)

    Returns:
        List of (output_name, path) tuples for created files
    """
    output_artifacts: List[tuple[str, Path]] = []

    # Placeholder: create stub outputs for module structure validation
    if include_summary:
        summary_path = output_dir / "summary.txt"
        summary_path.write_text(
            f"OpenFOAM case: {case_path.name}\n"
            f"Processors: {n_processors}\n"
            f"Output format: {output_format}\n"
            f"TODO: Implement foamRun, blockMesh, post-processing\n",
            encoding="utf-8",
        )
        output_artifacts.append(("summary", summary_path))

    results_path = output_dir / f"results.{output_format}"
    results_path.write_text(
        f"Placeholder results from case: {case_path}\n"
        f"TODO: Run foamRun and export via foamToVTK\n",
        encoding="utf-8",
    )
    output_artifacts.append(("results", results_path))

    log_path = output_dir / "log"
    log_path.write_text(
        "Placeholder solver log\nTODO: Capture foamRun stdout/stderr\n",
        encoding="utf-8",
    )
    output_artifacts.append(("log", log_path))

    return output_artifacts


def extract_case_if_archive(input_path: Path, temp_dir: Path) -> Path:
    """Extract case from .tgz/.tar.gz if needed; return path to case directory."""
    path = Path(input_path)
    if path.is_dir():
        return path
    name_lower = path.name.lower()
    if name_lower.endswith(".tgz") or name_lower.endswith(".tar.gz"):
        extract_to = temp_dir / "extracted_case"
        extract_to.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, "r:gz") as tf:
            tf.extractall(extract_to)
        extracted = list(extract_to.iterdir())
        if len(extracted) == 1 and extracted[0].is_dir():
            return extracted[0]
        return extract_to
    raise ValueError(f"Unsupported case format: {path}")


# ============================================================================
# FRAMEWORK CODE
# ============================================================================


class ModelParamsToArtifactsNoAuthInput(BaseModel):
    """
    Input schema for OpenFOAM ModelParamsToArtifactsNoAuth.

    Example input JSON:
    {
        "case": {"type": "user_model", "value": "/path/to/case.tgz"},
        "n_processors": {"type": "parameter", "value": 4},
        "include_summary": {"type": "parameter", "value": true},
        "output_format": {"type": "parameter", "value": "vtk"}
    }
    """

    case: Input[str] = Field(
        ...,
        description="OpenFOAM case: .tgz/.tar.gz archive or case directory path.",
    )

    n_processors: Optional[Input[int]] = Field(
        default=None,
        description="Number of MPI processes (default: 1)",
    )

    include_summary: Optional[Input[bool]] = Field(
        default=None,
        description="Whether to generate a summary file (default: True)",
    )

    output_format: Optional[Input[str]] = Field(
        default=None,
        description="Output format for results: vtk, csv, etc. (default: vtk)",
    )

    model_config = ConfigDict(extra=Extra.allow)


def model_params_to_artifacts_no_auth(input_json: str, temp_dir: str) -> List[Output]:
    """
    Process an OpenFOAM case with parameters and produce multiple artifacts.

    :param input_json: JSON string containing the function inputs.
    :param temp_dir: Directory for storing output files.
    :return: List containing multiple output artifacts.
    """
    logger.info("Starting ModelParamsToArtifactsNoAuth (OpenFOAM) execution.")

    try:
        function_input = ModelParamsToArtifactsNoAuthInput.model_validate_json(  # type: ignore[attr-defined]
            input_json,
        )
    except ValidationError as e:
        raise ValueError(
            f"Invalid input JSON for ModelParamsToArtifactsNoAuth: {e}",
        ) from e

    outputs: List[Output] = []
    case_input_path = Path(function_input.case.value)
    output_dir = Path(temp_dir)

    n_processors = (
        function_input.n_processors.value
        if function_input.n_processors is not None
        else 1
    )
    include_summary = (
        function_input.include_summary.value
        if function_input.include_summary is not None
        else True
    )
    output_format = (
        function_input.output_format.value
        if function_input.output_format is not None
        else "vtk"
    )

    logger.info(
        f"Processing case: n_processors={n_processors}, "
        f"include_summary={include_summary}, output_format={output_format}",
    )

    try:
        case_path = extract_case_if_archive(case_input_path, output_dir)
        output_artifacts = process_openfoam_case(
            case_path,
            output_dir,
            n_processors,
            include_summary,
            output_format,
        )
        for name, path in output_artifacts:
            outputs.append(
                Output(
                    name=name,
                    type=OutputType.FILE,
                    path=str(path.resolve()),
                ),
            )
    except (OSError, ValueError) as e:
        logger.exception(f"Failed to process case at {case_input_path}: {e}")
        raise ValueError(str(e)) from e

    return outputs


register("ModelParamsToArtifactsNoAuth", model_params_to_artifacts_no_auth)
