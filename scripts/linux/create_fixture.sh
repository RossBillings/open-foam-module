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
