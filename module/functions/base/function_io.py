from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class InputType(str, Enum):
    """
    Possible types of inputs expected by the module.
    """

    USER_MODEL = "user_model"
    PARAMETER = "parameter"
    AUTH_INFO = "auth_info"
    USER_LINK = "user_link"


class Input(BaseModel, Generic[T]):
    """
    An input item as defined by the Istari Agent.
    """

    type: InputType
    value: T

    model_config = ConfigDict(extra="allow")


class OutputType(str, Enum):
    """
    Possible types of outputs expected by the Istari Agent.
    """

    FILE = "file"
    DIRECTORY = "directory"


@dataclass
class Output:
    """
    An output item on disk pointed to by the path field.
    """

    name: str
    type: OutputType
    path: str
