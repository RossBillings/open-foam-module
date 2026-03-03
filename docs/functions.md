# OpenFOAM Module Functions

## `run_foam` — Run OpenFOAM Simulation

**What it does:** Full end-to-end solve pipeline.
1. Unzips the case archive
2. Reads `foam_job.json` config and validates case structure
3. Optionally overrides `endTime` and core count from inputs
4. If `mesh_required` is true and no mesh exists: runs `blockMesh`
5. Runs `foamRun` (serial) or `decomposePar` → `mpirun -np N foamRun -parallel` → `reconstructPar` (parallel)
6. Creates an empty `<case_name>.foam` file in the case root for ParaView
7. Runs any post-process utilities listed in `foam_job.json["post_process"]`
8. Parses the solver log for convergence signals and residuals
9. Copies all step logs into a `logs/` directory inside the case archive
10. Re-zips the solved case (with logs embedded)

**Inputs:**

| Name | Type | Required | Description |
|---|---|---|---|
| `foam_case` | `user_model` (`@extension:zip`) | Yes | OpenFOAM case archive (`.foam.zip`) |
| `override_end_time` | `parameter` (`@number`) | No | Override `endTime` in `controlDict` (seconds) |
| `override_np` | `parameter` (`@number`) | No | Override parallel core count (also sets `parallel: true` if > 1) |

**Artifacts:**

| Name | Required | Description |
|---|---|---|
| `solved_case` | Yes | Re-zipped case with all time directories, embedded logs, and `{case_name}.foam` ParaView touch file — `{case_name}_solved.foam.zip` |
| `run_log` | Yes | Raw `foamRun.log` from the solver |
| `convergence_report` | No | `convergence_report.json` — includes `converged`, `time_dirs_written`, `last_time`, `fields_at_last_time`, `control_dict` settings, `final_residuals`, `time_steps`, `execution_time_seconds`, `warnings`, and `errors` |

**`foam_job.json` fields used by `run_foam`:**

| Field | Type | Default | Description |
|---|---|---|---|
| `case_name` | string | required | Name of the case (used for zip file naming) |
| `foam_version` | string | required | OpenFOAM version (e.g. `"13"`) |
| `solver_module` | string | required | Solver name (e.g. `"incompressibleFluid"`) |
| `mesh_required` | boolean | `false` | Run `blockMesh` if no mesh exists |
| `parallel` | boolean | `false` | Run in parallel with `mpirun` |
| `np` | integer | `1` | Number of parallel processes |
| `post_process` | array of strings | `[]` | Post-processing commands to run after solving |

Example `convergence_report.json`:
```json
{
  "case_name": "cavity",
  "solver_module": "incompressibleFluid",
  "control_dict": {"endTime": "0.5", "deltaT": "0.005"},
  "time_dirs_written": ["0", "0.1", "0.2", "0.5"],
  "last_time": "0.5",
  "fields_at_last_time": ["U", "p"],
  "converged": true,
  "final_residuals": {"Ux": 1e-06, "p": 2e-06},
  "time_steps": [0.1, 0.2, 0.5],
  "execution_time_seconds": 2.1,
  "warnings": [],
  "errors": []
}
```

---

## `inspect_foam` — Inspect OpenFOAM Case

**What it does:** Lightweight pre-flight check — no solving.
1. Unzips case, validates directory structure
2. Reads `foam_job.json` and `controlDict` values
3. Reports mesh presence, `blockMeshDict`, `decomposeParDict`
4. Lists initial fields (`0/`) and existing time directories
5. Optionally runs `checkMesh` and captures key mesh quality lines

**Inputs:**

| Name | Type | Required | Description |
|---|---|---|---|
| `foam_case` | `user_model` (`@extension:zip`) | Yes | OpenFOAM case archive (`.foam.zip`) |
| `run_checkmesh` | `parameter` (`@boolean`) | No | Run `checkMesh` utility and include summary in report |

**Artifacts:**

| Name | Required | Description |
|---|---|---|
| `inspection_report` | Yes | `inspection_report.json` — structure validity, job config, controlDict, mesh status, initial fields, whether already solved, optional checkMesh summary |

Example `inspection_report.json`:
```json
{
  "structure_issues": [],
  "structure_valid": true,
  "foam_job": {"case_name": "cavity", "foam_version": "13", "solver_module": "incompressibleFluid"},
  "control_dict": {"application": "foamRun", "endTime": "0.5", "deltaT": "0.005"},
  "mesh_present": false,
  "blockmeshdict_present": true,
  "decompose_par_dict_present": false,
  "initial_fields": ["U", "p"],
  "time_dirs_present": ["0"],
  "already_solved": false
}
```

When `run_checkmesh: true` and a mesh exists, `checkmesh_returncode` and `checkmesh_summary` are also included.

---

## `patch_foam` — Patch OpenFOAM Parameters

**What it does:** Modifies case files without running the solver.
1. Unzips the case
2. Applies a list of `{file, key, value}` patches to OpenFOAM dict files via regex substitution
3. Merges any `foam_job.json` overrides
4. Optionally renames the case directory
5. Re-zips the modified case

**Inputs:**

| Name | Type | Required | Description |
|---|---|---|---|
| `foam_case` | `user_model` (`@extension:zip`) | Yes | OpenFOAM case archive (`.foam.zip`) |
| `patches` | `parameter` (`@string`) | No | JSON array of `{file, key, value}` patch objects (may be passed as JSON string) |
| `foam_job_patches` | `parameter` (`@string`) | No | JSON object of `foam_job.json` key overrides (may be passed as JSON string) |
| `output_case_name` | `parameter` (`@string`) | No | Rename the output case directory |

**Artifacts:**

| Name | Required | Description |
|---|---|---|
| `patched_case` | Yes | Re-zipped modified case — `{case_name}_patched.foam.zip` (or renamed if `output_case_name` set) |
| `patch_report` | Yes | `patch_report.json` — counts of succeeded/failed patches, per-patch detail, and `foam_job` overrides applied |

Example `patch_report.json`:
```json
{
  "patches_applied": 2,
  "patches_succeeded": 2,
  "patches_failed": 0,
  "detail": [
    {"file": "system/controlDict", "key": "endTime", "value": "20", "success": true, "reason": "OK"},
    {"file": "system/controlDict", "key": "deltaT", "value": "0.001", "success": true, "reason": "OK"}
  ],
  "foam_job_patches": {"np": 4, "parallel": true}
}
```

If a patch fails (key not found, file not found), `success` is `false` and `reason` explains why. Failed patches do not abort the run — the report captures all outcomes.
