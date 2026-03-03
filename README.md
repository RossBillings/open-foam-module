# OpenFOAM v13 Module

Istari module for OpenFOAM v13 CFD integration. Uses the **1 input + parameters → multiple outputs** pattern (`ModelParamsToArtifactsNoAuth`).

## Pattern

- **Input**: OpenFOAM case (`.tgz`/`.tar.gz` archive or case directory)
- **Parameters**: `n_processors`, `include_summary`, `output_format`
- **Outputs**: `summary`, `results`, `log`

## Quick Start

```bash
# Setup
poetry install

# Run tests
poetry run pytest

# Build executable (Linux)
poetry run poe build_binary_linux
```

## Manual Test

```bash
mkdir -p test_run
# Create a minimal case or use a .tgz archive
echo '{"case":{"type":"user_model","value":"test_run/case.tgz"},"n_processors":{"type":"parameter","value":1}}' > test_run/input.json

poetry run python -m module ModelParamsToArtifactsNoAuth \
  --input-file test_run/input.json \
  --output-file test_run/output.json \
  --temp-dir test_run
```

## Implementation Status

The module structure is in place. **TODO**: Implement actual OpenFOAM workflow in `process_openfoam_case()`:

- Source OpenFOAM environment
- Run `blockMesh`, `foamRun` (or `decomposePar` + `mpirun foamRun -parallel` + `reconstructPar`)
- Export results via `foamToVTK`
- Parse solver logs for summary

## Resources

- [TUTORIAL.md](./TUTORIAL.md): Step-by-step setup guide
- [DEVELOPMENT.md](./DEVELOPMENT.md): Development details
- [open_foam.md](../open_foam.md): OpenFOAM v13 concepts and workflow
