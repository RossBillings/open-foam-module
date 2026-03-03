# Linux Binary Build, Deploy & Test Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the openfoam module as a PyInstaller Linux binary, deploy to the OpenFOAM VM, create the cavity test fixture, and validate all three functions.

**Architecture:** Fix pyproject.toml to output the binary at `openfoam_module/openfoam_module` (matching the manifest), rsync source to the VM, build on the VM (PyInstaller must run on Linux), create a cavity fixture from OF v13 tutorials, then run two test tiers — pytest integration tests (Python module) and binary smoke tests (packaging validation).

**Tech Stack:** PyInstaller 6.x, Poetry/poe, pytest, SSH (`ssh openfoam`), rsync, OpenFOAM v13, bash

---

## Prerequisites

The VM is accessible via `ssh openfoam`. Python 3.12 and Poetry are already installed on the VM. OpenFOAM v13 is installed on the VM.

---

### Task 1: Fix binary output path in pyproject.toml

**Files:**
- Modify: `pyproject.toml` (line 55 — `[tool.poe.tasks]` section)

The current task outputs `dist/python_module`. The manifest expects `openfoam_module/openfoam_module`. Change both `--name` and add `--distpath`.

**Step 1: Edit pyproject.toml**

Replace the `build_binary` line in `[tool.poe.tasks]`:

```toml
[tool.poe.tasks]
build_binary = "pyinstaller --onefile --additional-hooks-dir=./hooks --name=openfoam_module --distpath=openfoam_module module/__main__.py"
```

**Step 2: Verify the change looks right**

Run: `grep build_binary pyproject.toml`
Expected: `build_binary = "pyinstaller --onefile --additional-hooks-dir=./hooks --name=openfoam_module --distpath=openfoam_module module/__main__.py"`

**Step 3: Commit**

```bash
cd /Users/rossbillings/github/integration-sdk
git add open-foam-module/pyproject.toml
git commit -m "fix: update poe build_binary to output openfoam_module/openfoam_module"
```

---

### Task 2: Create scripts/linux/create_fixture.sh

**Files:**
- Create: `open-foam-module/scripts/linux/create_fixture.sh`

This script creates `tests/integration/fixtures/cavity_test.foam.zip` from the OpenFOAM v13 cavity tutorial on the VM. The zip must have exactly one top-level directory (`cavity_test/`) as required by `unzip_case()`.

**Required `foam_job.json` fields** (from `read_foam_job` in `foam_utils.py`):
- `case_name`: must equal `"cavity_test"` (integration tests assert this)
- `foam_version`: `"13"`
- `solver_module`: `"incompressibleFluid"` (tests assert this)
- `mesh_required`: `true` (cavity tutorial has no pre-built polyMesh)
- `result_fields`: `["U", "p"]` (tests assert these fields are present)

**Step 1: Write the script**

```bash
cat > open-foam-module/scripts/linux/create_fixture.sh << 'SCRIPT'
#!/usr/bin/env bash
# Creates tests/integration/fixtures/cavity_test.foam.zip from OF v13 cavity tutorial.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FIXTURE_DIR="$PROJECT_ROOT/tests/integration/fixtures"

# Locate and source OpenFOAM bashrc
OF_BASHRC=""
for candidate in \
    /opt/openfoam13/etc/bashrc \
    /usr/lib/openfoam/openfoam13/etc/bashrc \
    /opt/OpenFOAM/OpenFOAM-13/etc/bashrc; do
    if [ -f "$candidate" ]; then
        OF_BASHRC="$candidate"
        break
    fi
done

if [ -z "$OF_BASHRC" ]; then
    echo "ERROR: Could not find OpenFOAM 13 bashrc. Tried:"
    echo "  /opt/openfoam13/etc/bashrc"
    echo "  /usr/lib/openfoam/openfoam13/etc/bashrc"
    echo "  /opt/OpenFOAM/OpenFOAM-13/etc/bashrc"
    exit 1
fi

source "$OF_BASHRC"

if [ -z "$FOAM_TUTORIALS" ]; then
    echo "ERROR: \$FOAM_TUTORIALS not set after sourcing $OF_BASHRC"
    exit 1
fi

CAVITY_SRC="$FOAM_TUTORIALS/incompressibleFluid/cavity"
if [ ! -d "$CAVITY_SRC" ]; then
    echo "ERROR: Cavity tutorial not found at $CAVITY_SRC"
    exit 1
fi

echo "Source: $CAVITY_SRC"
echo "Output: $FIXTURE_DIR/cavity_test.foam.zip"

mkdir -p "$FIXTURE_DIR"
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

# Copy cavity tutorial as cavity_test/
cp -r "$CAVITY_SRC" "$TMP/cavity_test"

# Write foam_job.json into the case root
cat > "$TMP/cavity_test/foam_job.json" << 'EOF'
{
  "case_name": "cavity_test",
  "foam_version": "13",
  "solver_module": "incompressibleFluid",
  "mesh_required": true,
  "np": 1,
  "result_fields": ["U", "p"]
}
EOF

# Zip with cavity_test/ as the single top-level directory
cd "$TMP"
zip -r "$FIXTURE_DIR/cavity_test.foam.zip" cavity_test/

echo "Done: $FIXTURE_DIR/cavity_test.foam.zip"
SCRIPT

chmod +x open-foam-module/scripts/linux/create_fixture.sh
```

**Step 2: Commit**

```bash
cd /Users/rossbillings/github/integration-sdk
git add open-foam-module/scripts/linux/create_fixture.sh
git commit -m "feat: add create_fixture.sh for cavity integration test fixture"
```

---

### Task 3: Rsync source to the VM

**Step 1: Create the remote build directory**

```bash
ssh openfoam "mkdir -p ~/openfoam_module_build"
```

**Step 2: Rsync the module source**

Run from the repo root:
```bash
cd /Users/rossbillings/github/integration-sdk
rsync -av --delete \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='openfoam_module' \
  --exclude='dist' \
  --exclude='.venv' \
  open-foam-module/ openfoam:~/openfoam_module_build/
```

Expected: file list printed, ends with something like `sent N bytes  received N bytes`

**Step 3: Verify key files arrived**

```bash
ssh openfoam "ls ~/openfoam_module_build/ && echo '---' && ls ~/openfoam_module_build/module/functions/"
```

Expected: see `pyproject.toml`, `module_manifest.json`, `module_config.json`, `scripts/` and under `functions/`: `run_foam.py`, `inspect_patch_foam.py`, `registry.py`

---

### Task 4: Build the binary on the VM

**Step 1: Install Python dependencies on the VM**

```bash
ssh openfoam "cd ~/openfoam_module_build && poetry install"
```

Expected: ends with `Installing the current project: open_foam (1.0.0)`

**Step 2: Run the build script**

```bash
ssh openfoam "cd ~/openfoam_module_build && bash scripts/linux/build.sh"
```

Expected: PyInstaller output ending with lines like:
```
Building EXE from EXE-00.toc completed successfully.
```

**Step 3: Confirm the binary exists at the expected path**

```bash
ssh openfoam "ls -lh ~/openfoam_module_build/openfoam_module/openfoam_module && file ~/openfoam_module_build/openfoam_module/openfoam_module"
```

Expected: ~30-60MB file, `ELF 64-bit LSB executable`

**Step 4: Quick sanity check — binary prints help**

```bash
ssh openfoam "~/openfoam_module_build/openfoam_module/openfoam_module --help"
```

Expected: argparse help output listing `function_name`, `--input-file`, `--output-file`, `--temp-dir`, `--config-path`

---

### Task 5: Create the cavity fixture on the VM

**Step 1: Run the fixture creation script**

```bash
ssh openfoam "cd ~/openfoam_module_build && bash scripts/linux/create_fixture.sh"
```

Expected output:
```
Source: /opt/openfoam13/tutorials/incompressibleFluid/cavity   (path may vary)
Output: .../tests/integration/fixtures/cavity_test.foam.zip
Done: .../tests/integration/fixtures/cavity_test.foam.zip
```

**Step 2: Verify the zip structure**

```bash
ssh openfoam "cd ~/openfoam_module_build && python3 -c \"
import zipfile
with zipfile.ZipFile('tests/integration/fixtures/cavity_test.foam.zip') as zf:
    entries = sorted(set(n.split('/')[0] for n in zf.namelist()))
    print('Top-level dirs:', entries)
    foam_job = [n for n in zf.namelist() if 'foam_job.json' in n]
    print('foam_job.json:', foam_job)
\""
```

Expected:
```
Top-level dirs: ['cavity_test']
foam_job.json: ['cavity_test/foam_job.json']
```

---

### Task 6: Run pytest integration tests on the VM

`inspect_foam` and `patch_foam` tests do NOT require OpenFOAM to be installed. `run_foam` tests DO require it. Run all together — pytest will skip `run_foam` if OF isn't on PATH after sourcing, but we should source it first.

**Step 1: Source OpenFOAM and run all integration tests**

```bash
ssh openfoam "cd ~/openfoam_module_build && source \$(
  for f in /opt/openfoam13/etc/bashrc /usr/lib/openfoam/openfoam13/etc/bashrc; do
    [ -f \"\$f\" ] && echo \"\$f\" && break
  done
) && poetry run pytest tests/integration/ -v -s 2>&1 | tee /tmp/pytest_integration.log"
```

**Step 2: Review results**

```bash
ssh openfoam "tail -30 /tmp/pytest_integration.log"
```

Expected: All tests pass. `test_patch_foam_value_persisted_in_zip` may fail — this test imports from the gitignored `lib/` path (known pre-existing issue, not blocking).

**Step 3: If run_foam tests are skipped (OpenFOAM not on PATH)**

Check the OF bashrc path on the VM:
```bash
ssh openfoam "find /opt /usr/lib -name 'bashrc' 2>/dev/null | grep openfoam"
```
Then retry with the correct path.

---

### Task 7: Binary smoke tests on the VM

These tests call the compiled binary (not `python3 -m module`) to validate PyInstaller packaging is correct. One test per function.

**Step 1: Prepare temp dirs and write input files**

```bash
ssh openfoam "mkdir -p /tmp/foam_smoke/{run,inspect,patch}/tmp"
```

The `test_files/` JSON inputs already point to `tests/integration/fixtures/cavity_test.foam.zip`. We need absolute paths:

```bash
ssh openfoam "cd ~/openfoam_module_build && python3 -c \"
import json, pathlib
fixture = str(pathlib.Path('tests/integration/fixtures/cavity_test.foam.zip').resolve())

run_input = {
    'foam_case': {'type': 'user_model', 'value': fixture},
    'override_end_time': {'type': 'parameter', 'value': 0.05},
    'override_np': {'type': 'parameter', 'value': 1}
}
inspect_input = {
    'foam_case': {'type': 'user_model', 'value': fixture},
    'run_checkmesh': {'type': 'parameter', 'value': False}
}
patch_input = {
    'foam_case': {'type': 'user_model', 'value': fixture},
    'patches': {'type': 'parameter', 'value': json.dumps([{'file': 'system/controlDict', 'key': 'endTime', 'value': '2.0'}])},
    'foam_job_patches': {'type': 'parameter', 'value': '{}'},
    'output_case_name': {'type': 'parameter', 'value': 'cavity_patched'}
}
pathlib.Path('/tmp/foam_smoke/run/input.json').write_text(json.dumps(run_input))
pathlib.Path('/tmp/foam_smoke/inspect/input.json').write_text(json.dumps(inspect_input))
pathlib.Path('/tmp/foam_smoke/patch/input.json').write_text(json.dumps(patch_input))
print('Input files written.')
\""
```

**Step 2: Smoke test inspect_foam (no OpenFOAM needed)**

```bash
ssh openfoam "~/openfoam_module_build/openfoam_module/openfoam_module inspect_foam \
  --input-file /tmp/foam_smoke/inspect/input.json \
  --output-file /tmp/foam_smoke/inspect/output.json \
  --temp-dir /tmp/foam_smoke/inspect/tmp \
  --config-path ~/openfoam_module_build/module_config.json && \
  echo '--- output.json ---' && cat /tmp/foam_smoke/inspect/output.json"
```

Expected: JSON array with one entry containing `name: "inspection_report"` and an absolute path.

**Step 3: Smoke test patch_foam (no OpenFOAM needed)**

```bash
ssh openfoam "~/openfoam_module_build/openfoam_module/openfoam_module patch_foam \
  --input-file /tmp/foam_smoke/patch/input.json \
  --output-file /tmp/foam_smoke/patch/output.json \
  --temp-dir /tmp/foam_smoke/patch/tmp \
  --config-path ~/openfoam_module_build/module_config.json && \
  echo '--- output.json ---' && cat /tmp/foam_smoke/patch/output.json"
```

Expected: JSON array with entries `patched_case` and `patch_report`, both with absolute paths.

**Step 4: Smoke test run_foam (requires OpenFOAM on PATH)**

Source OF before invoking the binary. `override_end_time: 0.05` keeps the run short (~a few seconds for the cavity tutorial).

```bash
ssh openfoam "
OF_BASHRC=''
for f in /opt/openfoam13/etc/bashrc /usr/lib/openfoam/openfoam13/etc/bashrc; do
  [ -f \"\$f\" ] && OF_BASHRC=\"\$f\" && break
done
source \$OF_BASHRC
~/openfoam_module_build/openfoam_module/openfoam_module run_foam \
  --input-file /tmp/foam_smoke/run/input.json \
  --output-file /tmp/foam_smoke/run/output.json \
  --temp-dir /tmp/foam_smoke/run/tmp \
  --config-path ~/openfoam_module_build/module_config.json && \
echo '--- output.json ---' && cat /tmp/foam_smoke/run/output.json"
```

Expected: JSON array with `solved_case`, `run_log`, `convergence_report`. Check convergence:
```bash
ssh openfoam "python3 -c \"
import json
outputs = json.loads(open('/tmp/foam_smoke/run/output.json').read())
conv_path = next(o['path'] for o in outputs if o['name'] == 'convergence_report')
report = json.loads(open(conv_path).read())
print('converged:', report['converged'])
print('time_dirs:', report['time_dirs_written'])
\""
```

Expected: `converged: True`, `time_dirs` contains `['0.05']` or similar.

---

### Task 8: Pull the binary back to the local repo

Once all tests pass, copy the Linux binary back to the local repo so it's ready for packaging.

**Step 1: Create the local output directory**

```bash
mkdir -p /Users/rossbillings/github/integration-sdk/open-foam-module/openfoam_module
```

**Step 2: Copy binary from VM**

```bash
scp openfoam:~/openfoam_module_build/openfoam_module/openfoam_module \
    /Users/rossbillings/github/integration-sdk/open-foam-module/openfoam_module/openfoam_module
```

**Step 3: Verify**

```bash
ls -lh /Users/rossbillings/github/integration-sdk/open-foam-module/openfoam_module/openfoam_module
file /Users/rossbillings/github/integration-sdk/open-foam-module/openfoam_module/openfoam_module
```

Expected: ELF 64-bit executable, ~30-60MB.

**Step 4: Add binary directory to .gitignore (binaries are not committed)**

```bash
grep -q "^openfoam_module/$" /Users/rossbillings/github/integration-sdk/open-foam-module/.gitignore || \
  echo "openfoam_module/" >> /Users/rossbillings/github/integration-sdk/open-foam-module/.gitignore
```

**Step 5: Commit .gitignore if changed**

```bash
cd /Users/rossbillings/github/integration-sdk
git diff open-foam-module/.gitignore
git add open-foam-module/.gitignore
git commit -m "chore: gitignore compiled openfoam_module binary directory"
```

---

## Known Issues

- `test_patch_foam_value_persisted_in_zip` imports `from foam_utils import read_of_value` using the gitignored `lib/` path. This test will fail with ImportError. It is a pre-existing issue in the test, not caused by this work — skip or fix it separately.
- If `module_config.json` has `openfoam_bin_dir` set, the binary will prepend that to PATH automatically. If not set and OF is already on PATH (via sourcing bashrc before invocation), no change needed.
