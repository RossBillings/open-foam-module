# Linux Binary Build & Test Design

**Date:** 2026-03-03
**Status:** Approved

## Goal

Build the openfoam module as a PyInstaller Linux binary, deploy it to the OpenFOAM VM, and validate all three functions (`run_foam`, `inspect_foam`, `patch_foam`) end-to-end.

## Context

- Build tool: PyInstaller (already in dev dependencies)
- Target: Ubuntu 22.04 VM accessible via `ssh openfoam`
- VM has Python 3.12 + Poetry installed; OpenFOAM v13 installed
- Manifest entrypoint: `openfoam_module/openfoam_module`
- Current pyproject.toml names binary `python_module` — must be fixed

## Phases

### Phase 1 — Fix binary output path (local)

Update `pyproject.toml` poe task to match the manifest's expected path:
- `--name=openfoam_module`
- `--distpath=openfoam_module`

Produces: `openfoam_module/openfoam_module`

### Phase 2 — Sync source to VM

```bash
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='openfoam_module' \
  open-foam-module/ openfoam:~/openfoam_module_build/
```

### Phase 3 — Build binary on VM

```bash
ssh openfoam "cd ~/openfoam_module_build && poetry install && bash scripts/linux/build.sh"
```

`scripts/linux/build.sh` already handles Python dev headers check and calls `poetry run poe build_binary`.

### Phase 4 — Create cavity fixture on VM

Write `scripts/linux/create_fixture.sh` that:
1. Sources OpenFOAM 13 (`/opt/openfoam13/etc/bashrc` or equivalent)
2. Copies `$FOAM_TUTORIALS/incompressibleFluid/cavity` → temp `cavity_test/`
3. Writes `foam_job.json` into `cavity_test/`
4. Zips with `cavity_test/` as the top-level directory
5. Places result at `tests/integration/fixtures/cavity_test.foam.zip`

### Phase 5 — Two-tier testing on VM

**Tier 1 — pytest integration (tests Python module directly):**
```bash
ssh openfoam "cd ~/openfoam_module_build && source <OF_bashrc> && poetry run pytest tests/integration/ -v -s"
```

**Tier 2 — binary smoke test (validates PyInstaller packaging):**
Invoke the binary directly for each of the 3 functions using `test_files/` JSON inputs, checking `output.json` is written and required files exist.

## Success Criteria

- Binary exists at `openfoam_module/openfoam_module` on the VM
- All pytest integration tests pass
- Binary smoke tests produce valid `output.json` for all 3 functions
