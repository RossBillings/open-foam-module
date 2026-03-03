# Python Module Reference Guide

This document provides detailed reference material for developing Istari modules with Python. For a quick introduction, see the [Quick Start Tutorial](TUTORIAL.md).

## Table of Contents

1. [Project Structure](#project-structure)
2. [Manual Testing](#manual-testing)
3. [Configuration](#configuration)
4. [Building and Deploying](#building-and-deploying)
5. [Advanced Topics](#advanced-topics)
6. [Common Patterns](#common-patterns)
7. [Troubleshooting](#troubleshooting)

---

## Project Structure

### Directory Layout

```
python-module-scaffold/
├── module/                      # Main module package
│   ├── __main__.py             # Entry point (CLI interface)
│   ├── module_config.py        # Configuration management
│   ├── logging_config.py       # Logging setup
│   └── functions/              # Your functions go here
│       ├── __init__.py         # Auto-loads functions
│       ├── registry.py         # Function registry
│       ├── data_extraction.py  # Example function
│       └── base/
│           └── function_io.py  # Input/Output types
├── tests/                      # Your tests
├── module_manifest.json        # Platform registration
├── module_config.json          # Default configuration
├── pyproject.toml              # Dependencies and build config
└── README.md                   # Project documentation
```

### Key Files Explained

- **`module/__main__.py`**: Handles CLI arguments and orchestrates function execution.
- **`module/functions/`**: Where you write your business logic.
- **`module_manifest.json`**: Defines your module's functions for the Istari platform.
- **`module_config.json`**: Default configuration values.
- **`pyproject.toml`**: Python project configuration and dependencies.

### Auto-Discovery

The scaffold automatically discovers functions. Any new Python file you add to `module/functions/` (except `base/` and `registry.py`) will be automatically imported by `module/functions/__init__.py`, ensuring your functions are registered when the module starts.

---

## Manual Testing

Before deploying, test your module manually using both Poetry (development) and the built executable (production).

### Step 1: Create Test Files

Create a `test_run` directory with a test input file:

**Linux/Mac:**
```bash
mkdir -p test_run
echo "Hello world this is a test file with some content." > test_run/input.txt
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType Directory -Force -Path test_run
"Hello world this is a test file with some content." | Out-File -Encoding utf8 test_run/input.txt
```

Create `test_run/input.json` with your editor:

```json
{
    "text_file": {
        "type": "user_model",
        "value": "test_run/input.txt"
    }
}
```

### Step 2: Run with Poetry (Development Mode)

```bash
poetry run python -m module YourFunction --input-file test_run/input.json --output-file test_run/output.json --temp-dir test_run
```

### Step 3: Check Results

**Linux/Mac:**
```bash
cat test_run/output.json
```

**Windows (PowerShell):**
```powershell
Get-Content test_run/output.json
```

### Step 4: Build and Test Executable

```bash
poetry run poe build_binary
```

**Linux/Mac:**
```bash
./dist/python_module YourFunction --input-file test_run/input.json --output-file test_run/output.json --temp-dir test_run
```

**Windows:**
```powershell
.\dist\python_module.exe YourFunction --input-file test_run/input.json --output-file test_run/output.json --temp-dir test_run
```

### Testing with Parameters

For functions with parameters, create `test_run/input_params.json`:

```json
{
    "input_model": {
        "type": "user_model",
        "value": "test_run/input.txt"
    },
    "include_summary": {
        "type": "parameter",
        "value": true
    },
    "max_lines": {
        "type": "parameter",
        "value": 10
    }
}
```

### Testing with Authentication

For auth-enabled functions, create `test_run/auth.json`:

```json
{
    "username": "user",
    "password": "pass"
}
```

And `test_run/input_auth.json`:

```json
{
    "input_model": {
        "type": "user_model",
        "value": "test_run/input.txt"
    },
    "auth_info": {
        "type": "auth_info",
        "value": "test_run/auth.json"
    }
}
```

### Testing Error Handling

```bash
# Test with invalid function name (should exit with code 1)
poetry run python -m module InvalidFunction --input-file test_run/input.json --output-file test_run/output.json --temp-dir test_run
```

### Cleanup

**Linux/Mac:**
```bash
rm -rf test_run
```

**Windows (PowerShell):**
```powershell
Remove-Item -Recurse -Force test_run
```

---

## Configuration

Modules can be configured via `module_config.json`. There are two ways to provide this configuration:

1. **Default Configuration**: A `module_config.json` file placed in the same directory as the executable.
2. **Agent Configuration (Production)**: The Istari Agent generates a config file and passes its path to your module.

### Defining Your Configuration

Update `module/module_config.py` to define the structure of your configuration:

```python
class ModuleConfig(BaseModel):
    log_level: LogLevel = Field(default=LogLevel.INFO)
    log_file_path: Path = Field(default=DEFAULT_LOG_FILE)

    # Add your custom config
    my_custom_setting: int = Field(
        default=1,
        description="Description of your setting"
    )
```

### Using Configuration in Your Function

The scaffold automatically loads the configuration for you:

```python
from module import module_config
import sys
from pathlib import Path

def my_function(input_json: str, temp_dir: str) -> List[Output]:
    # Access the loaded config
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path.cwd()

    config_path = base_dir / "module_config.json"
    config = module_config.load_config(str(config_path))

    # Use config value
    setting = config.my_custom_setting
```

### Setting Default Configuration

Update `module_config.json` with your default values:

```json
{
  "log_level": "INFO",
  "log_file_path": "module.log",
  "my_custom_setting": 3
}
```

### Enabling Agent Configuration

To allow the Istari Agent to pass configuration to your module in production:

1. **Update `module_manifest.json`**:

```json
{
  "additional_configuration_required": true,
  "functions": {
    "@istari:extract": [
      {
        "run_command": "{entrypoint} MyFunction ... --config-path {config_path}"
      }
    ]
  }
}
```

2. **Configure the Agent** in `istari_digital_config.yaml`:

```yaml
istari_digital_agent_module_configurations:
  "@istari:python_scaffold":
    "my_custom_setting": 5
```

When the Agent runs your module, it will automatically generate a JSON config file with these values and pass its path via the `--config-path` argument.

---

## Building and Deploying

### Building the Executable

Build a standalone executable using PyInstaller:

```bash
poetry run poe build_binary
```

This creates `dist/python_module` (Linux/Mac) or `dist/python_module.exe` (Windows).

### Testing the Built Executable

Test your built executable:

```bash
# Linux/Mac
./dist/python_module MyFunction --input-file test_input.json --output-file output.json --temp-dir ./temp

# Windows
dist\python_module.exe MyFunction --input-file test_input.json --output-file output.json --temp-dir .\temp
```

### Deployment Checklist

- [ ] All functions tested locally
- [ ] Executable builds successfully
- [ ] Executable tested on target OS
- [ ] `module_manifest.json` updated with correct function schemas
- [ ] `module_config.json` has sensible defaults
- [ ] Documentation updated

---

## Advanced Topics

### Input and Output Types

- **`Input[T]`**: A generic wrapper for input fields that separates the metadata from the value. `Input[str]` usually wraps a file path string.
- **`Output`**: Represents a file or artifact produced by your module. It includes the `name` (key in manifest), `type` (usually `FILE`), and the `path` to the file on disk.

### Multiple Functions

You can define multiple functions in the same module. Each function should be in its own file and registered:

```python
# module/functions/function_a.py
def function_a(input_json: str, temp_dir: str) -> List[Output]:
    # ...
register("FunctionA", function_a)

# module/functions/function_b.py
def function_b(input_json: str, temp_dir: str) -> List[Output]:
    # ...
register("FunctionB", function_b)
```

Both will be automatically discovered when the module loads.

### Error Handling

Handle errors gracefully:

```python
def robust_function(input_json: str, temp_dir: str) -> List[Output]:
    outputs = []

    try:
        input_data = MyInput.model_validate_json(input_json)
    except ValidationError as e:
        logger.error(f"Invalid input: {e}")
        return outputs

    try:
        result = process_file(input_data.file_path.value)
    except Exception as e:
        logger.exception("Processing failed")
        error_file = Path(temp_dir) / "error_report.txt"
        error_file.write_text(f"Error: {e}\n")
        outputs.append(Output(
            name="error_report",
            type=OutputType.FILE,
            path=str(error_file)
        ))
        return outputs

    return outputs
```

### Logging

Use the module logger for debugging:

```python
import logging

logger = logging.getLogger(__name__)

def my_function(input_json: str, temp_dir: str) -> List[Output]:
    logger.debug("Detailed debug information")
    logger.info("General information")
    logger.warning("Something unexpected happened")
    logger.error("An error occurred")
    logger.exception("Exception with traceback")
```

Logs are written to the file specified in `module_config.json`.

### Complex Input Schemas

Handle multiple inputs and optional parameters:

```python
from typing import Optional
from pydantic import BaseModel, Field

class ComplexInput(BaseModel):
    required_file: Input[str] = Field(..., description="Required input file")
    optional_file: Optional[Input[str]] = Field(None, description="Optional file")
    parameters: Optional[dict] = Field(None, description="Optional parameters")

def complex_function(input_json: str, temp_dir: str) -> List[Output]:
    input_data = ComplexInput.model_validate_json(input_json)

    process_file(input_data.required_file.value)

    if input_data.optional_file:
        process_file(input_data.optional_file.value)

    if input_data.parameters:
        use_option = input_data.parameters.get("option", "default")
```

---

## Common Patterns

### Pattern 1: File Processing

Process a file and generate multiple outputs:

```python
def process_file(input_json: str, temp_dir: str) -> List[Output]:
    input_data = FileInput.model_validate_json(input_json)
    file_path = Path(input_data.file.value)
    temp_path = Path(temp_dir)

    outputs = []

    result1 = process_part1(file_path)
    output1 = temp_path / "result1.txt"
    output1.write_text(result1)
    outputs.append(Output(name="result1", type=OutputType.FILE, path=str(output1)))

    result2 = process_part2(file_path)
    output2 = temp_path / "result2.json"
    output2.write_text(json.dumps(result2))
    outputs.append(Output(name="result2", type=OutputType.FILE, path=str(output2)))

    return outputs
```

### Pattern 2: API Integration

Call an external API:

```python
import requests

def api_function(input_json: str, temp_dir: str) -> List[Output]:
    input_data = APIInput.model_validate_json(input_json)

    response = requests.post(
        "https://api.example.com/process",
        json={"data": input_data.data.value}
    )
    response.raise_for_status()

    result_file = Path(temp_dir) / "api_result.json"
    result_file.write_text(response.text)

    return [Output(name="api_result", type=OutputType.FILE, path=str(result_file))]
```

### Pattern 3: External Tool Integration

Call an external command-line tool:

```python
import subprocess
from pathlib import Path

def tool_function(input_json: str, temp_dir: str) -> List[Output]:
    input_data = ToolInput.model_validate_json(input_json)
    input_file = input_data.file.value
    output_file = Path(temp_dir) / "tool_output.txt"

    result = subprocess.run(
        ["external_tool", "--input", input_file, "--output", str(output_file)],
        capture_output=True,
        text=True,
        check=True
    )

    return [Output(name="tool_output", type=OutputType.FILE, path=str(output_file))]
```

### Pattern 4: Directory Processing

Process all files in a directory:

```python
def process_directory(input_json: str, temp_dir: str) -> List[Output]:
    input_data = DirectoryInput.model_validate_json(input_json)
    directory = Path(input_data.directory.value)
    outputs = []

    for file_path in directory.glob("*.txt"):
        result = process_file(file_path)
        output_file = Path(temp_dir) / f"{file_path.stem}_processed.txt"
        output_file.write_text(result)
        outputs.append(Output(
            name=f"{file_path.stem}_processed",
            type=OutputType.FILE,
            path=str(output_file)
        ))

    return outputs
```

---

## Troubleshooting

### Function Not Found

**Problem**: `ValueError: Function "MyFunction" is not registered`

**Solution**:
- Ensure you called `register("MyFunction", my_function)` at the bottom of your function file
- Check that the function name matches exactly (case-sensitive)
- Verify the function module is imported (check `module/functions/__init__.py` auto-discovery logic if needed)

### Input Validation Errors

**Problem**: `ValueError: Invalid input JSON`

**Solution**:
- Check your input JSON matches the Pydantic model exactly
- Verify field names match (case-sensitive)
- Ensure required fields are present
- Check data types match (string, number, etc.)

### File Not Found Errors

**Problem**: `OSError: Could not read file`

**Solution**:
- Verify file paths in input JSON are absolute or correct relative paths
- Check file permissions
- Ensure files exist before processing
- Use `Path.exists()` to check before reading

### Output Not Written

**Problem**: Output file missing or empty

**Solution**:
- Check `temp_dir` exists and is writable
- Verify you're writing to `Path(temp_dir) / "filename"` not just `"filename"`
- Check file permissions
- Ensure you're returning Output objects with correct paths

### Import Errors

**Problem**: `ModuleNotFoundError` or `ImportError`

**Solution**:
- Ensure all dependencies are in `pyproject.toml`
- Run `poetry install` to install dependencies
- Check Python path and virtual environment activation
- Verify module structure matches imports

### Build Errors

**Problem**: PyInstaller build fails

**Solution**:
- Check all imports are available
- Verify `pyproject.toml` has all dependencies
- Check PyInstaller hooks if using special libraries
- Review build logs for specific missing modules

### Function Works Locally But Not in Executable

**Problem**: Function works with `python -m module` but fails when built

**Solution**:
- Check that all data files are included in PyInstaller build
- Verify paths work when frozen (use `sys.executable` for base path)
- Check that external tools/dependencies are available in deployment environment
- Test the executable directly, not just the Python script
