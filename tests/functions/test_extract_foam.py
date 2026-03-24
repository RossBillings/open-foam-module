"""
Unit tests for extract_foam utility functions in foam_utils.py.
Tests: parse_of_field_file, read_initial_conditions,
       read_physical_properties, read_turbulence_properties,
       compute_field_statistics
"""

from pathlib import Path

import numpy as np
import pytest

from module.services.foam_utils import (
    compute_field_statistics,
    parse_of_field_file,
    read_initial_conditions,
    read_physical_properties,
    read_turbulence_properties,
)


# ---------------------------------------------------------------------------
# Fixtures / sample content
# ---------------------------------------------------------------------------

VECTOR_FIELD = """\
FoamFile { class volVectorField; object U; }
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    movingWall
    {
        type            fixedValue;
        value           uniform (1 0 0);
    }
    fixedWalls
    {
        type            noSlip;
    }
    frontAndBack
    {
        type            empty;
    }
}
"""

SCALAR_FIELD = """\
FoamFile { class volScalarField; object p; }
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    movingWall
    {
        type            zeroGradient;
    }
    fixedWalls
    {
        type            zeroGradient;
    }
}
"""

PHYSICAL_PROPS_V13 = """\
FoamFile { object physicalProperties; }
viscosityModel  constant;
nu              1e-05;
"""

PHYSICAL_PROPS_OLD = """\
FoamFile { object transportProperties; }
transportModel  Newtonian;
nu              nu [0 2 -1 0 0 0 0] 1e-06;
rho             rho [1 -3 0 0 0 0 0] 1000;
"""

MOMENTUM_TRANSPORT_RAS = """\
FoamFile { object momentumTransport; }
simulationType  RAS;
RAS
{
    model           kEpsilon;
    turbulence      on;
}
"""

TURBULENCE_PROPS_LAMINAR = """\
FoamFile { object turbulenceProperties; }
simulationType  laminar;
"""


# ---------------------------------------------------------------------------
# parse_of_field_file
# ---------------------------------------------------------------------------

def test_parse_field_dimensions_vector(tmp_path):
    f = tmp_path / "U"
    f.write_text(VECTOR_FIELD)
    result = parse_of_field_file(f)
    assert result["dimensions"] == "[0 1 -1 0 0 0 0]"


def test_parse_field_dimensions_scalar(tmp_path):
    f = tmp_path / "p"
    f.write_text(SCALAR_FIELD)
    result = parse_of_field_file(f)
    assert result["dimensions"] == "[0 2 -2 0 0 0 0]"


def test_parse_field_internal_field_vector(tmp_path):
    f = tmp_path / "U"
    f.write_text(VECTOR_FIELD)
    result = parse_of_field_file(f)
    assert result["internal_field"] == "uniform (0 0 0)"


def test_parse_field_internal_field_scalar(tmp_path):
    f = tmp_path / "p"
    f.write_text(SCALAR_FIELD)
    result = parse_of_field_file(f)
    assert result["internal_field"] == "uniform 0"


def test_parse_field_boundaries_types(tmp_path):
    f = tmp_path / "U"
    f.write_text(VECTOR_FIELD)
    result = parse_of_field_file(f)
    boundaries = result["boundaries"]
    assert boundaries["movingWall"]["type"] == "fixedValue"
    assert boundaries["fixedWalls"]["type"] == "noSlip"
    assert boundaries["frontAndBack"]["type"] == "empty"


def test_parse_field_boundary_value(tmp_path):
    f = tmp_path / "U"
    f.write_text(VECTOR_FIELD)
    result = parse_of_field_file(f)
    assert result["boundaries"]["movingWall"]["value"] == "uniform (1 0 0)"


def test_parse_field_boundary_no_value_key(tmp_path):
    """Boundaries without a value entry (e.g. noSlip) should have no value key."""
    f = tmp_path / "U"
    f.write_text(VECTOR_FIELD)
    result = parse_of_field_file(f)
    assert "value" not in result["boundaries"]["fixedWalls"]


# ---------------------------------------------------------------------------
# read_initial_conditions
# ---------------------------------------------------------------------------

def test_read_initial_conditions_field_names(tmp_path):
    case = tmp_path / "cavity"
    (case / "0").mkdir(parents=True)
    (case / "0" / "U").write_text(VECTOR_FIELD)
    (case / "0" / "p").write_text(SCALAR_FIELD)

    ic = read_initial_conditions(case)
    assert "U" in ic
    assert "p" in ic


def test_read_initial_conditions_empty_when_no_zero_dir(tmp_path):
    case = tmp_path / "cavity"
    case.mkdir()
    assert read_initial_conditions(case) == {}


def test_read_initial_conditions_field_structure(tmp_path):
    case = tmp_path / "cavity"
    (case / "0").mkdir(parents=True)
    (case / "0" / "U").write_text(VECTOR_FIELD)

    ic = read_initial_conditions(case)
    assert "dimensions" in ic["U"]
    assert "internal_field" in ic["U"]
    assert "boundaries" in ic["U"]


# ---------------------------------------------------------------------------
# read_physical_properties
# ---------------------------------------------------------------------------

def test_read_physical_properties_v13(tmp_path):
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    (case / "constant" / "physicalProperties").write_text(PHYSICAL_PROPS_V13)

    props = read_physical_properties(case)
    assert props["nu"] == "1e-05"
    assert props["viscosityModel"] == "constant"


def test_read_physical_properties_prefers_v13(tmp_path):
    """physicalProperties takes priority over transportProperties when both exist."""
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    (case / "constant" / "physicalProperties").write_text(PHYSICAL_PROPS_V13)
    (case / "constant" / "transportProperties").write_text(PHYSICAL_PROPS_OLD)

    props = read_physical_properties(case)
    assert props.get("viscosityModel") == "constant"


def test_read_physical_properties_empty_when_missing(tmp_path):
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    assert read_physical_properties(case) == {}


# ---------------------------------------------------------------------------
# read_turbulence_properties
# ---------------------------------------------------------------------------

def test_read_turbulence_properties_ras(tmp_path):
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    (case / "constant" / "momentumTransport").write_text(MOMENTUM_TRANSPORT_RAS)

    turb = read_turbulence_properties(case)
    assert turb["simulationType"] == "RAS"
    assert turb["model"] == "kEpsilon"
    assert turb["turbulence"] == "on"


def test_read_turbulence_properties_laminar(tmp_path):
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    (case / "constant" / "turbulenceProperties").write_text(TURBULENCE_PROPS_LAMINAR)

    turb = read_turbulence_properties(case)
    assert turb["simulationType"] == "laminar"
    assert "model" not in turb


def test_read_turbulence_properties_empty_when_missing(tmp_path):
    case = tmp_path / "cavity"
    (case / "constant").mkdir(parents=True)
    assert read_turbulence_properties(case) == {}


# ---------------------------------------------------------------------------
# compute_field_statistics
# ---------------------------------------------------------------------------

def _write_scalar_field(path: Path, values: list[float]) -> None:
    n = len(values)
    lines = "\n".join(str(v) for v in values)
    path.write_text(
        f"FoamFile {{ class volScalarField; }}\n"
        f"internalField   nonuniform List<scalar>\n"
        f"{n}\n(\n{lines}\n);\n"
    )


def _write_vector_field(path: Path, vectors: list[tuple[float, float, float]]) -> None:
    n = len(vectors)
    lines = "\n".join(f"({x} {y} {z})" for x, y, z in vectors)
    path.write_text(
        f"FoamFile {{ class volVectorField; }}\n"
        f"internalField   nonuniform List<vector>\n"
        f"{n}\n(\n{lines}\n);\n"
    )


def test_compute_field_statistics_scalar(tmp_path):
    case = tmp_path / "cavity"
    time_dir = case / "1.0"
    time_dir.mkdir(parents=True)
    _write_scalar_field(time_dir / "p", [1.0, 2.0, 3.0, 4.0])

    stats = compute_field_statistics(case, "1.0", ["p"])
    assert "p" in stats
    assert stats["p"]["min"] == pytest.approx(1.0)
    assert stats["p"]["max"] == pytest.approx(4.0)
    assert stats["p"]["mean"] == pytest.approx(2.5)


def test_compute_field_statistics_vector(tmp_path):
    case = tmp_path / "cavity"
    time_dir = case / "1.0"
    time_dir.mkdir(parents=True)
    _write_vector_field(time_dir / "U", [(1.0, 0.0, 0.0), (2.0, 0.0, 0.0)])

    stats = compute_field_statistics(case, "1.0", ["U"])
    assert "U" in stats
    assert "magnitude" in stats["U"]
    assert "x" in stats["U"]
    assert stats["U"]["x"]["min"] == pytest.approx(1.0)
    assert stats["U"]["x"]["max"] == pytest.approx(2.0)
    assert stats["U"]["magnitude"]["min"] == pytest.approx(1.0)
    assert stats["U"]["magnitude"]["max"] == pytest.approx(2.0)


def test_compute_field_statistics_missing_field(tmp_path):
    """Missing field file is silently skipped."""
    case = tmp_path / "cavity"
    (case / "1.0").mkdir(parents=True)

    stats = compute_field_statistics(case, "1.0", ["nonexistent"])
    assert stats == {}


def test_compute_field_statistics_multiple_fields(tmp_path):
    case = tmp_path / "cavity"
    time_dir = case / "1.0"
    time_dir.mkdir(parents=True)
    _write_scalar_field(time_dir / "p", [0.0, 10.0])
    _write_vector_field(time_dir / "U", [(1.0, 0.0, 0.0), (3.0, 0.0, 0.0)])

    stats = compute_field_statistics(case, "1.0", ["p", "U"])
    assert "p" in stats
    assert "U" in stats
