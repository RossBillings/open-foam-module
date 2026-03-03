import json
import uuid
from pathlib import Path
from typing import Dict

from module import module_config
from module.module_config import ModuleConfig


def test_load_config_with_valid_config_file(tmp_path: Path):
    """
    Configuration should be loaded correctly from valid configuration files.
    """
    log_level: str = "warning"
    log_file_path = tmp_path.joinpath("temp_log_file")
    config_dict: Dict[str, str] = {
        "log_level": log_level,
        "log_file_path": str(log_file_path),
    }
    config_file_path = tmp_path.joinpath("config_file.json")
    with config_file_path.open("w") as config_file:
        json.dump(config_dict, config_file)

    config: ModuleConfig = module_config.load_config(config_file_path)

    assert config is not None
    assert config.log_level.value.lower() == log_level
    assert config.log_file_path == log_file_path


def test_load_config_with_invalid_config_file(tmp_path: Path):
    """
    Default configuration should be loaded if an invalid path is passed.
    """
    nonexisting_file = tmp_path.joinpath(str(uuid.uuid4()))

    loaded_config: ModuleConfig = module_config.load_config(nonexisting_file)
    default_config = ModuleConfig()

    assert loaded_config is not None
    assert loaded_config.log_level == default_config.log_level
    assert loaded_config.log_file_path == default_config.log_file_path


def test_config_with_extra_fields(tmp_path: Path) -> None:
    """
    Extra fields should not prevent correct fields from configuring the module properly.
    """
    log_level: str = "critical"
    log_file_path = tmp_path.joinpath("temp_log_file")
    config_dict: Dict[str, str] = {
        "log_level": log_level,
        "log_file_path": str(log_file_path),
        "extra_field": "extra_value",
    }
    config_file_path = tmp_path.joinpath("config_file.json")
    with config_file_path.open("w") as config_file:
        json.dump(config_dict, config_file)

    config: ModuleConfig = module_config.load_config(config_file_path)

    assert config is not None
    assert config.log_level.value.lower() == log_level
    assert config.log_file_path == log_file_path


def test_load_config_with_os_error(tmp_path: Path):
    """
    Default configuration should be loaded if an OSError occurs when reading the file.
    """
    from unittest.mock import mock_open, patch

    config_file_path = tmp_path.joinpath("config_file.json")

    with patch("builtins.open", mock_open()) as mock_file:
        mock_file.side_effect = OSError("Permission denied")

        loaded_config: ModuleConfig = module_config.load_config(
            str(config_file_path),
        )
        default_config = ModuleConfig()

        assert loaded_config is not None
        assert loaded_config.log_level == default_config.log_level
        assert loaded_config.log_file_path == default_config.log_file_path


def test_load_config_with_invalid_json(tmp_path: Path):
    """
    Default configuration should be loaded if the config file contains invalid JSON.
    """
    config_file_path = tmp_path.joinpath("config_file.json")
    with config_file_path.open("w") as config_file:
        config_file.write("invalid json content {")

    loaded_config: ModuleConfig = module_config.load_config(str(config_file_path))
    default_config = ModuleConfig()

    assert loaded_config is not None
    assert loaded_config.log_level == default_config.log_level
    assert loaded_config.log_file_path == default_config.log_file_path
