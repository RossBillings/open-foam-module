"""
module/services/foam_viz.py

Matplotlib-based visualization utilities for OpenFOAM postprocessing.

Functions:
  plot_convergence()     — semilogy residual history → PNG
  plot_field_contour()   — 2D filled contour of a field → PNG
  plot_mesh_quality()    — bar chart + metrics table from checkMesh → PNG

All functions are headless (Agg backend) and return True on success,
False if matplotlib/numpy is unavailable or the data is insufficient.
"""

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def plot_convergence(
    residuals: dict[str, list[tuple[float, float, float]]],
    output_path: str,
) -> bool:
    """
    Plot solver convergence history on a semilogy scale.

    residuals: {field: [(time_step, initial_residual, final_residual), ...]}
    Returns True if the PNG was written successfully.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not available; skipping convergence plot")
        return False

    fig, ax = plt.subplots(figsize=(10, 6))
    has_data = False
    for field, data in residuals.items():
        if data:
            times = [d[0] for d in data]
            init_res = [d[1] for d in data]
            ax.semilogy(times, init_res, label=field, linewidth=1.5)
            has_data = True

    if not has_data:
        plt.close(fig)
        return False

    ax.set_xlabel("Time Step")
    ax.set_ylabel("Initial Residual")
    ax.set_title("Solver Convergence History")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Wrote convergence plot: %s", output_path)
    return True


def plot_field_contour(
    field_array: Any,
    mesh_dims: tuple[int, int],
    field_name: str,
    output_path: str,
) -> bool:
    """
    Plot a 2D filled contour of a field at final time.

    field_array: numpy array — (n,) for scalar, (n, 3) for vector (magnitude is plotted).
    mesh_dims:   (nx, ny) cell counts from blockMeshDict.
    Returns True if the PNG was written successfully.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        log.warning("matplotlib/numpy not available; skipping contour plot for %s", field_name)
        return False

    try:
        nx, ny = mesh_dims
        arr = np.asarray(field_array, dtype=float)

        if arr.ndim == 2 and arr.shape[1] == 3:
            arr = np.linalg.norm(arr, axis=1)

        if arr.size != nx * ny:
            log.warning(
                "Field %s has %d values but mesh is %dx%d (%d cells); skipping contour",
                field_name, arr.size, nx, ny, nx * ny,
            )
            return False

        data_2d = arr.reshape((ny, nx))
        x = np.linspace(0, 1, nx)
        y = np.linspace(0, 1, ny)

        label = f"|{field_name}|" if field_array.ndim == 2 else field_name

        fig, ax = plt.subplots(figsize=(7, 7))
        cf = ax.contourf(x, y, data_2d, levels=20, cmap="jet")
        fig.colorbar(cf, ax=ax, label=label)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(f"{label} — Final Time")
        ax.set_aspect("equal")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("Wrote contour plot: %s", output_path)
        return True
    except Exception as exc:
        log.warning("Failed to plot contour for %s: %s", field_name, exc)
        return False


def plot_mesh_quality(
    checkmesh: dict[str, Any],
    output_path: str,
) -> bool:
    """
    Plot a mesh quality summary: topology counts (bar) + quality metrics (table).

    checkmesh: output of parse_checkmesh_output().
    Returns True if the PNG was written successfully.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not available; skipping mesh quality plot")
        return False

    if not checkmesh:
        return False

    try:
        fig, (ax_bar, ax_tbl) = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("checkMesh Quality Report", fontsize=13, fontweight="bold")

        # Left: bar chart of topology counts
        count_keys = [k for k in ("cells", "faces", "points") if k in checkmesh]
        if count_keys:
            values = [checkmesh[k] for k in count_keys]
            colours = ["#4C72B0", "#DD8452", "#55A868"]
            bars = ax_bar.bar(count_keys, values, color=colours[: len(count_keys)])
            for bar, val in zip(bars, values):
                ax_bar.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    f"{val:,}",
                    ha="center", va="bottom", fontsize=9,
                )
            ax_bar.set_title("Mesh Topology")
            ax_bar.set_ylabel("Count")
        else:
            ax_bar.set_visible(False)

        # Right: quality metrics table
        metric_map = [
            ("max_non_orthogonality", "Max Non-Orthogonality (°)"),
            ("max_skewness", "Max Skewness"),
            ("mesh_ok", "Mesh OK"),
        ]
        rows = [
            [label, str(checkmesh[key])]
            for key, label in metric_map
            if key in checkmesh
        ]
        if rows:
            ax_tbl.axis("off")
            tbl = ax_tbl.table(
                cellText=rows,
                colLabels=["Metric", "Value"],
                loc="center",
                cellLoc="center",
            )
            tbl.auto_set_font_size(True)
            tbl.scale(1.2, 2.0)
            ax_tbl.set_title("Quality Metrics")
        else:
            ax_tbl.set_visible(False)

        fig.tight_layout()
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("Wrote mesh quality plot: %s", output_path)
        return True
    except Exception as exc:
        log.warning("Failed to plot mesh quality: %s", exc)
        return False
