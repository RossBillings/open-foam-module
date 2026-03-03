# Python Module Scaffold

[![Test Status](https://github.com/Istari-digital/python-module-scaffold/actions/workflows/tests.yml/badge.svg)](https://github.com/Istari-digital/python-module-scaffold/actions/workflows/tests.yml)
[![Build Status](https://github.com/Istari-digital/python-module-scaffold/actions/workflows/build.yml/badge.svg)](https://github.com/Istari-digital/python-module-scaffold/actions/workflows/build.yml)

This is repository contains a template intended to speed up internal development of Istari Agent modules developed in Python.

The structure shown and decisions made on where and how to write functionality is merely a suggestion based on frequent and common behaviors of Istari Agent modules and the tools they interact with. Since all tools behave differently, its expected that the actual implementation deviates from the template based whatever purpose the agent module fullfils.

## Development Environment

The project uses Python versions `>=3.11,<3.13`, and `poetry` for dependency management. Create a virtual environment and install the dependencies like so:

```bash
python3 -m venv venv
source venv/bin/activate # or ./venv/Scripts/activate on Windows
pip install poetry
poetry install
```

The main runtime dependency introduced by the template is [Pydantic](https://docs.pydantic.dev/), which provides the needed validation and schema checking to avoid integration issues. Build tools such as [PyInstaller](https://pyinstaller.org/) (for packaging executables) and linting/formatting tools like [Black](https://black.readthedocs.io/) are included as dev dependencies and pre-commit hooks.

Pre-commit hooks for formatting and linting can be installed through `pre-commit` by running:

```bash
poetry run pre-commit install
```

### Testing and Test Coverage

Tests are run via `pytest`. Pytest is configured to check test coverage and fail the test workflow if test coverage is below 80%. (This is the  company target for test coverage that all repos deployed into production should achieve.) The minimum test coverage and the set of files that test coverage is calculated on can be adjusted in `pyproject.toml` in the `[tool.coverage]` sections. Test coverage information is printed to the console when the test script is run.

### Local Secret Checking

We have integrated a pre-commit step that utilizes [TruffleHog](https://github.com/trufflesecurity/trufflehog) for local secret checking. If truffleHog is not already installed, it will be automatically installed by pre-commit, hence developers do not need to initiate this installation process manually. It's important to note that this project uses TrufflehogV3 (3.88.10).

## Project Structure

```bash
python-module
├── module
│   ├── functions # Istari platform functions exposed by the module, following a common interface.
│   └── utils # Common utilities.
└── tests # Unit and integration tests
```

## Usage

To execute a function use the following command line parameters:

`python3 -m module {function_name} --input-file {input_file} --output-file {output_file} --temp-dir {temp-dir}`

- `function_name`: `function name` is the name of the function as recorded in the function schema.
- `--input-file`: `input_file` must exist and contain inputs to the function according to the function schema. The
- `--outpu-file`: `output_file` will be created by the module containing output data according to the function schema.
- `--temp-dir`: `temp-dir` is directory that must exist. If called with the Istari Agent, the Istari Agent will clean up all contents of the temp-dir after the module has completed executing.

When creating a new function, add a Python file in the `module/functions/` folder. Define a plain function that takes
`input_json` (a JSON string) and `temp_dir` (a directory path) as parameters, and returns a list of `Output` objects.

```python
from pydantic import BaseModel
from module.functions.base.function_io import Input, Output, OutputType
from module.functions.registry import register

# Define your input model with Pydantic
class MyFunctionInput(BaseModel):
    input_file: Input[str]

# Write your function
def my_function(input_json: str, temp_dir: str) -> list[Output]:
    # Parse input
    input_data = MyFunctionInput.model_validate_json(input_json)

    # Do your work here
    # ...

    # Return outputs
    return [Output(name="result", type=OutputType.FILE, path="...")]

# Register the function (name must match module_manifest.json)
register("MyFunction", my_function)
```

The function name used in `register()` **must match** the name provided in the function schema in `module_manifest.json`.

The function returns a list of `Output` objects. The module will write these outputs to the `output_file.json`.
The list of Outputs must match the output schema defined in `module_manifest.json`, although order may be different.

## Building and Deployment

You can build the executable like so when in your virtual environment:

```bash
poetry run poe build_binary
```

You would find the executable in the `dist` directory.

Releases are created automatically when a valid SemVer tag is pushed to the repository.
