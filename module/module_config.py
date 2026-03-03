import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Extra, Field, ValidationError

from module.logging_config import LogLevel

logger = logging.getLogger(__name__)

DEFAULT_LOG_FILE = Path("python_module.log")


class ModuleConfig(BaseModel):
    """
    Configuration settings for the module. Add configurable fields to this class. Make sure to provide default values
    whenever possible to reduce the amount of configuration fields needed to run the module.
    """

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="The log level for the module",
    )

    log_file_path: Path = Field(
        default=DEFAULT_LOG_FILE,
        description="Path to the log file to write logs to.",
    )

    openfoam_bin_dir: Optional[str] = Field(
        default=None,
        description="Path to the OpenFOAM bin directory (e.g. /opt/openfoam13/bin). "
                    "If null, OpenFOAM commands are resolved from the system PATH.",
    )

    model_config = ConfigDict(extra=Extra.allow)


def load_config(config_file_path: str) -> ModuleConfig:
    try:
        with open(config_file_path, "r") as config_file:
            config_data: str = config_file.read()
        config = ModuleConfig.model_validate_json(config_data)  # type: ignore[attr-defined]
        return config
    except FileNotFoundError:
        logger.warning(
            f'Did not find a configuration file at "{config_file_path}". Loading default configuration.',
        )
    except OSError:
        logger.warning(
            "Could not read configuration file provided due to an I/O error. Loading default configuration.",
        )
    except ValidationError:
        logger.warning(
            "Configuration file provided is not valid. Ensure that the configuration is a JSON object with key/value pairs for each configuration item. Loading default configuration.",
        )

    config = ModuleConfig()
    return config
