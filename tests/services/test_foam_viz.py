"""
Unit tests for module/services/foam_viz.py

Covers plot_convergence, plot_field_contour, plot_mesh_quality.
"""

import numpy as np
import pytest

from module.services.foam_viz import plot_convergence, plot_field_contour, plot_mesh_quality


# ---------------------------------------------------------------------------
# plot_convergence
# ---------------------------------------------------------------------------

def test_plot_convergence_writes_png(tmp_path):
    """Returns True and writes a PNG when given valid residual data."""
    residuals = {
        "Ux": [(0.1, 1e-1, 1e-2), (0.2, 5e-2, 5e-3)],
        "p":  [(0.1, 1e-2, 1e-3), (0.2, 5e-3, 5e-4)],
    }
    out = tmp_path / "conv.png"
    result = plot_convergence(residuals, str(out))
    assert result is True
    assert out.exists()


def test_plot_convergence_empty_data_returns_false(tmp_path):
    """Returns False and writes no file when all fields have empty data."""
    out = tmp_path / "conv.png"
    result = plot_convergence({"Ux": []}, str(out))
    assert result is False
    assert not out.exists()


def test_plot_convergence_empty_dict_returns_false(tmp_path):
    """Returns False for empty residuals dict."""
    out = tmp_path / "conv.png"
    result = plot_convergence({}, str(out))
    assert result is False


# ---------------------------------------------------------------------------
# plot_field_contour
# ---------------------------------------------------------------------------

def test_plot_field_contour_scalar_writes_png(tmp_path):
    """Scalar field with matching mesh dims writes PNG."""
    nx, ny = 10, 10
    arr = np.linspace(0, 1, nx * ny)
    out = tmp_path / "p_contour.png"
    result = plot_field_contour(arr, (nx, ny), "p", str(out))
    assert result is True
    assert out.exists()


def test_plot_field_contour_vector_writes_png(tmp_path):
    """Vector field (n,3) uses magnitude and writes PNG."""
    nx, ny = 5, 5
    arr = np.ones((nx * ny, 3))
    out = tmp_path / "U_contour.png"
    result = plot_field_contour(arr, (nx, ny), "U", str(out))
    assert result is True
    assert out.exists()


def test_plot_field_contour_size_mismatch_returns_false(tmp_path):
    """Returns False when array size does not match nx*ny."""
    arr = np.zeros(50)
    out = tmp_path / "p_contour.png"
    result = plot_field_contour(arr, (10, 10), "p", str(out))
    assert result is False
    assert not out.exists()


# ---------------------------------------------------------------------------
# plot_mesh_quality
# ---------------------------------------------------------------------------

def test_plot_mesh_quality_writes_png(tmp_path):
    """Returns True and writes PNG for valid checkmesh dict."""
    checkmesh = {
        "cells": 1000,
        "faces": 4000,
        "points": 1200,
        "max_non_orthogonality": 45.2,
        "max_skewness": 0.8,
        "mesh_ok": True,
    }
    out = tmp_path / "mesh_quality.png"
    result = plot_mesh_quality(checkmesh, str(out))
    assert result is True
    assert out.exists()


def test_plot_mesh_quality_empty_returns_false(tmp_path):
    """Returns False for empty checkmesh dict."""
    out = tmp_path / "mesh_quality.png"
    result = plot_mesh_quality({}, str(out))
    assert result is False
    assert not out.exists()


def test_plot_mesh_quality_no_counts_still_writes(tmp_path):
    """Works even with only quality metrics (no cell/face/point counts)."""
    checkmesh = {
        "max_non_orthogonality": 30.0,
        "max_skewness": 0.5,
        "mesh_ok": True,
    }
    out = tmp_path / "mesh_quality.png"
    result = plot_mesh_quality(checkmesh, str(out))
    assert result is True
    assert out.exists()
