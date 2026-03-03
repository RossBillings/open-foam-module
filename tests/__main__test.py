"""Tests for module/__main__.py"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from module import __main__
from module.functions.base.function_io import Output, OutputType


def test_main_with_valid_args(tmp_path: Path):
    """Test that main() correctly parses arguments and calls run()."""
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    temp_dir = str(tmp_path / "temp")

    # Create input file (OpenFOAM case)
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()
    input_data = {"case": {"type": "user_model", "value": str(case_dir)}}
    with input_file.open("w") as f:
        json.dump(input_data, f)

    # Create temp directory
    os.makedirs(temp_dir, exist_ok=True)

    with patch("module.__main__.run") as mock_run:
        with patch(
            "sys.argv",
            [
                "module",
                "ModelParamsToArtifactsNoAuth",
                "--input-file",
                str(input_file),
                "--output-file",
                str(output_file),
                "--temp-dir",
                temp_dir,
            ],
        ):
            __main__.main()
            mock_run.assert_called_once_with(
                "ModelParamsToArtifactsNoAuth",
                str(input_file),
                str(output_file),
                temp_dir,
                None,
            )


def test_run_successful_execution(tmp_path: Path):
    """Test successful execution of run() function."""
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    temp_dir = str(tmp_path / "temp")

    # Create input file (OpenFOAM case)
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()
    input_data = {"case": {"type": "user_model", "value": str(case_dir)}}
    with input_file.open("w") as f:
        json.dump(input_data, f)

    # Create temp directory
    os.makedirs(temp_dir, exist_ok=True)

    # Mock the function to return outputs
    mock_outputs = [
        Output(name="test_output", type=OutputType.FILE, path="test.txt"),
    ]

    with patch("module.__main__.get_function") as mock_get_function:
        mock_function = MagicMock(return_value=mock_outputs)
        mock_get_function.return_value = mock_function

        with patch("module.__main__.logging_config.configure_initial_logging"):
            with patch("module.__main__.module_config.load_config") as mock_load_config:
                from module.logging_config import LogLevel
                from module.module_config import ModuleConfig

                mock_config = ModuleConfig(
                    log_level=LogLevel.INFO,
                    log_file_path=tmp_path / "test.log",
                )
                mock_load_config.return_value = mock_config

                with patch("module.__main__.logging_config.configure_logging"):
                    __main__.run(
                        "ModelParamsToArtifactsNoAuth",
                        str(input_file),
                        str(output_file),
                        temp_dir,
                    )

    # Verify output file was written
    assert output_file.exists()
    with output_file.open("r") as f:
        output_data = json.load(f)
        assert len(output_data) == 1
        assert output_data[0]["name"] == "test_output"


def test_run_with_frozen_executable(tmp_path: Path):
    """Test run() when executed from PyInstaller (frozen)."""
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    temp_dir = str(tmp_path / "temp")

    # Create input file (OpenFOAM case)
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()
    input_data = {"case": {"type": "user_model", "value": str(case_dir)}}
    with input_file.open("w") as f:
        json.dump(input_data, f)

    # Create temp directory
    os.makedirs(temp_dir, exist_ok=True)

    mock_outputs = [
        Output(name="test_output", type=OutputType.FILE, path="test.txt"),
    ]

    with patch("module.__main__.get_function") as mock_get_function:
        mock_function = MagicMock(return_value=mock_outputs)
        mock_get_function.return_value = mock_function

        with patch("module.__main__.logging_config.configure_initial_logging"):
            with patch("module.__main__.module_config.load_config") as mock_load_config:
                from module.logging_config import LogLevel
                from module.module_config import ModuleConfig

                mock_config = ModuleConfig(
                    log_level=LogLevel.INFO,
                    log_file_path=tmp_path / "test.log",
                )
                mock_load_config.return_value = mock_config

                with patch("module.__main__.logging_config.configure_logging"):
                    with patch("sys.frozen", True, create=True):
                        with patch("sys.executable", str(tmp_path / "executable.exe")):
                            __main__.run(
                                "ModelParamsToArtifactsNoAuth",
                                str(input_file),
                                str(output_file),
                                temp_dir,
                            )

    # Verify config was loaded from executable directory
    mock_load_config.assert_called_once()
    call_args = mock_load_config.call_args[0][0]
    assert "module_config.json" in call_args


def test_run_input_file_read_error(tmp_path: Path):
    """Test run() when input file cannot be read."""
    input_file = tmp_path / "nonexistent.json"
    output_file = tmp_path / "output.json"
    temp_dir = str(tmp_path / "temp")

    with patch("module.__main__.logging_config.configure_initial_logging"):
        with patch("module.__main__.module_config.load_config") as mock_load_config:
            from module.logging_config import LogLevel
            from module.module_config import ModuleConfig

            mock_config = ModuleConfig(
                log_level=LogLevel.INFO,
                log_file_path=tmp_path / "test.log",
            )
            mock_load_config.return_value = mock_config

            with patch("module.__main__.logging_config.configure_logging"):
                with pytest.raises(SystemExit) as exc_info:
                    __main__.run(
                        "ModelParamsToArtifactsNoAuth",
                        str(input_file),
                        str(output_file),
                        temp_dir,
                    )
                    assert exc_info.value.code == 1


def test_run_function_not_found(tmp_path: Path):
    """Test run() when function is not registered."""
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    temp_dir = str(tmp_path / "temp")

    # Create input file
    input_data = {"text_file": {"type": "user_model", "value": "test.txt"}}
    with input_file.open("w") as f:
        json.dump(input_data, f)

    with patch("module.__main__.get_function") as mock_get_function:
        mock_get_function.side_effect = ValueError("Function not found")

        with patch("module.__main__.logging_config.configure_initial_logging"):
            with patch("module.__main__.module_config.load_config") as mock_load_config:
                from module.logging_config import LogLevel
                from module.module_config import ModuleConfig

                mock_config = ModuleConfig(
                    log_level=LogLevel.INFO,
                    log_file_path=tmp_path / "test.log",
                )
                mock_load_config.return_value = mock_config

                with patch("module.__main__.logging_config.configure_logging"):
                    with pytest.raises(SystemExit) as exc_info:
                        __main__.run(
                            "NonExistentFunction",
                            str(input_file),
                            str(output_file),
                            temp_dir,
                        )
                        assert exc_info.value.code == 1


def test_run_function_execution_error(tmp_path: Path):
    """Test run() when function raises ValueError during execution."""
    input_file = tmp_path / "input.json"
    output_file = tmp_path / "output.json"
    temp_dir = str(tmp_path / "temp")

    # Create input file (OpenFOAM case)
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()
    input_data = {"case": {"type": "user_model", "value": str(case_dir)}}
    with input_file.open("w") as f:
        json.dump(input_data, f)

    with patch("module.__main__.get_function") as mock_get_function:
        # Mock function that raises ValueError (like auth functions do)
        mock_function = MagicMock(side_effect=ValueError("Invalid auth file"))
        mock_get_function.return_value = mock_function

        with patch("module.__main__.logging_config.configure_initial_logging"):
            with patch("module.__main__.module_config.load_config") as mock_load_config:
                from module.logging_config import LogLevel
                from module.module_config import ModuleConfig

                mock_config = ModuleConfig(
                    log_level=LogLevel.INFO,
                    log_file_path=tmp_path / "test.log",
                )
                mock_load_config.return_value = mock_config

                with patch("module.__main__.logging_config.configure_logging"):
                    with pytest.raises(SystemExit) as exc_info:
                        __main__.run(
                            "SomeFunction",
                            str(input_file),
                            str(output_file),
                            temp_dir,
                        )
                    assert exc_info.value.code == 1


def test_run_output_file_write_error(tmp_path: Path):
    """Test run() when output file cannot be written."""
    input_file = tmp_path / "input.json"
    temp_dir = str(tmp_path / "temp")

    # Create input file (OpenFOAM case)
    case_dir = tmp_path / "cavity"
    case_dir.mkdir()
    input_data = {"case": {"type": "user_model", "value": str(case_dir)}}
    with input_file.open("w") as f:
        json.dump(input_data, f)

    # Create temp directory
    os.makedirs(temp_dir, exist_ok=True)

    mock_outputs = [
        Output(name="test_output", type=OutputType.FILE, path="test.txt"),
    ]

    with patch("module.__main__.get_function") as mock_get_function:
        mock_function = MagicMock(return_value=mock_outputs)
        mock_get_function.return_value = mock_function

        with patch("module.__main__.logging_config.configure_initial_logging"):
            with patch("module.__main__.module_config.load_config") as mock_load_config:
                from module.logging_config import LogLevel
                from module.module_config import ModuleConfig

                mock_config = ModuleConfig(
                    log_level=LogLevel.INFO,
                    log_file_path=tmp_path / "test.log",
                )
                mock_load_config.return_value = mock_config

                with patch("module.__main__.logging_config.configure_logging"):
                    # Make output file write fail by using invalid path
                    invalid_output_file = Path("/invalid/path/output.json")

                    # Should not raise exception, just log error
                    __main__.run(
                        "ModelParamsToArtifactsNoAuth",
                        str(input_file),
                        str(invalid_output_file),
                        temp_dir,
                    )


def test_command_args_dataclass():
    """Test CommandArgs dataclass."""
    args = __main__.CommandArgs(
        function_name="TestFunction",
        input_file="input.json",
        output_file="output.json",
        temp_dir="/tmp",
        config_path="config.json",
    )

    assert args.function_name == "TestFunction"
    assert args.input_file == "input.json"
    assert args.output_file == "output.json"
    assert args.temp_dir == "/tmp"
    assert args.config_path == "config.json"
