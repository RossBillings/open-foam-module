# Quick Start: Build Your First Istari Module

This guide walks you through creating and running your first Istari module function in about 10 minutes.

## What is an Istari Module?

An Istari module is a standalone executable that integrates with the Istari platform. Modules expose **functions** that process files and return results.

> **Learn more:** For detailed documentation on how modules work, see [Introduction to Istari Integrations](https://docs.istaridigital.com/developers/Integrations%20SDK/integrations-sdk-intro).

---

## Prerequisites

- **Python 3.11 or 3.12** ([Download](https://www.python.org/downloads/))
- **Poetry** for dependency management

**Install Poetry via pipx (recommended):**

```bash
python -m pip install --user pipx
python -m pipx ensurepath
pipx install poetry
```

**Verify your setup:**

```bash
python --version  # Should show 3.11.x or 3.12.x
poetry --version  # Should show Poetry version
```

---

## Step 1: Create Your Project

```bash
# Using the Istari CLI (recommended)
stari module scaffold my-module --type python-module
cd my-module

# Or clone directly
git clone --depth=1 https://github.com/istaridigital/python-module-scaffold my-module
cd my-module
```

Update `pyproject.toml` with your project details:

```toml
[tool.poetry]
name = "my-module"
version = "0.1.0"
description = "My first Istari module"
authors = ["Your Name <your.email@example.com>"]
```

---

## Step 2: Install Dependencies

```bash
poetry install
```

Verify the scaffold works:

```bash
poetry run pytest
```

---

## Step 3: Create Your First Function

Create `module/functions/file_copy.py`:

```python
import logging
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel
from module.functions.base.function_io import Input, Output, OutputType
from module.functions.registry import register

logger = logging.getLogger(__name__)


class FileCopyInput(BaseModel):
    input_file: Input[str]


def file_copy(input_json: str, temp_dir: str) -> list[Output]:
    """Copies input file to output with a timestamp header."""
    input_data = FileCopyInput.model_validate_json(input_json)

    # Read input
    input_path = Path(input_data.input_file.value)
    content = input_path.read_text()

    # Write output with header
    output_path = Path(temp_dir) / "copied_file.txt"
    header = f"# Processed at {datetime.now().isoformat()}\n\n"
    output_path.write_text(header + content)

    logger.info(f"Copied {input_path} to {output_path}")

    return [Output(name="copied_file", type=OutputType.FILE, path=str(output_path))]


register("FileCopy", file_copy)
```

---

## Step 4: Register Your Function in the Manifest

Add your function to `module_manifest.json` so the Istari platform knows about it. Add this entry to the `functions` object:

```json
{
  "functions": {
    "@istari:extract": [
      {
        "entrypoint": "python_module",
        "run_command": "{entrypoint} FileCopy --input-file {input_file} --output-file {output_file} --temp-dir {temp_dir}",
        "function_schema": {
          "inputs": {
            "input_file": {
              "type": "user_model",
              "validation_types": ["@extension:txt"]
            }
          },
          "outputs": [
            {
              "name": "copied_file",
              "type": "file",
              "required": false
            }
          ]
        },
        "operating_systems": ["Ubuntu 22.04", "Windows 10", "Windows 11"],
        "tool_versions": ["3.11"]
      }
    ]
  }
}
```

**Important:** The function name `"FileCopy"` in `run_command` must match the name used in `register()`.

---

## Step 5: Run Your Function

**Create a test input file** (`test_run/input.txt`):

```bash
mkdir test_run
echo "Hello, Istari!" > test_run/input.txt
```

**Create the input JSON** (`test_run/input.json`):

```json
{
    "input_file": {
        "type": "user_model",
        "value": "test_run/input.txt"
    }
}
```

**Run your function:**

```bash
poetry run python -m module FileCopy \
    --input-file test_run/input.json \
    --output-file test_run/output.json \
    --temp-dir test_run
```

**Check the results:**

```bash
cat test_run/output.json
# [{"name": "copied_file", "type": "file", "path": "test_run/copied_file.txt"}]

cat test_run/copied_file.txt
# # Processed at 2024-01-15T10:30:00.000000
#
# Hello, Istari!
```

---

## Next Steps

You've successfully created and run your first Istari module function!

**Continue learning:**

- **[REFERENCE.md](REFERENCE.md)** — Detailed guide covering project structure, configuration, testing, common patterns, and troubleshooting
- **[Introduction to Istari Integrations](https://docs.istaridigital.com/developers/Integrations%20SDK/integrations-sdk-intro)** — How modules work in the Istari platform
- **[Authoring Integrations with the Istari CLI](https://docs.istaridigital.com/developers/Integrations%20SDK/istari-cli-integrations-management)** — CLI tools for scaffolding, validation, and publishing
- **[Module Manifest API Reference](https://docs.istaridigital.com/developers/Integrations%20SDK/API%20Reference/api-reference)** — Complete manifest specification

**Build and deploy:**

```bash
poetry run poe build_binary
# Creates dist/python_module.exe (Windows) or dist/python_module (Linux/Mac)
```

See [REFERENCE.md](REFERENCE.md) for the full deployment checklist.
