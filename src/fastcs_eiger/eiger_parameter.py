from dataclasses import dataclass
from typing import Any, Literal

from fastcs.datatypes import Bool, DataType, Float, Int, String
from pydantic import BaseModel


class EigerParameterResponse(BaseModel):
    access_mode: str
    allowed_values: Any | None = None
    value: Any
    value_type: Literal["float", "int", "bool", "str"]

    @property
    def fastcs_datatype(self) -> DataType:
        match self.value_type:
            case "float":
                return Float()
            case "int":
                return Int()
            case "bool":
                return Bool()
            case "str":
                return String()
            case _:
                raise ValueError(f"Unsupported data type: {self.value_type}")


@dataclass
class EigerParameter:
    key: str
    """Last section of URI within a subsystem/mode."""
    subsystem: Literal["detector", "stream", "monitor"]
    """Subsystem within detector API."""
    mode: Literal["status", "config"]
    """Mode of parameter within subsystem."""
    response: EigerParameterResponse
    """JSON response from GET of parameter."""

    @property
    def attribute_name(self):
        return key_to_attribute_name(self.key)

    @property
    def uri(self) -> str:
        """Full URI for HTTP requests."""
        return f"{self.subsystem}/api/1.8.0/{self.mode}/{self.key}"


EIGER_PARAMETER_SUBSYSTEMS = EigerParameter.__annotations__["subsystem"].__args__
EIGER_PARAMETER_MODES = EigerParameter.__annotations__["mode"].__args__


def key_to_attribute_name(key: str):
    return key.replace("/", "_")
