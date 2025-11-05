from dataclasses import dataclass
from typing import Any, Literal

from fastcs.datatypes import Bool, DataType, Float, Int, String
from pydantic import BaseModel
from fastcs.attribute_io_ref import AttributeIORef


class EigerParameterResponse(BaseModel):
    access_mode: Literal["r", "w", "rw"]
    allowed_values: Any | None = None
    min: float | int | None = None
    value: Any
    value_type: Literal[
        "float", "int", "bool", "uint", "string", "datetime", "State", "string[]"
    ]

@dataclass(kw_only=True)
class EigerParameterRef(AttributeIORef):
    update_period: float | None = 0.2
    """Poll period for parameter"""
    key: str
    """Last section of URI within a subsystem/mode."""
    subsystem: Literal["detector", "stream", "monitor"]
    """Subsystem within detector API."""
    mode: Literal["status", "config"]   # TODO, we need to make a different ref class for each mode...
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

    @property
    def fastcs_datatype(self) -> DataType:
        match self.response.value_type:
            case "float":
                return Float(prec=minimum_to_precision(self.response.min))
            case "int" | "uint":
                return Int()
            case "bool":
                return Bool()
            case "string" | "datetime" | "State" | "string[]":
                return String()


EIGER_PARAMETER_SUBSYSTEMS = EigerParameterRef.__annotations__["subsystem"].__args__
EIGER_PARAMETER_MODES = EigerParameterRef.__annotations__["mode"].__args__


def key_to_attribute_name(key: str):
    return key.replace("/", "_")


def minimum_to_precision(value: float | None) -> int:
    if value is not None:
        value_as_str = str(value)
        if "." in value_as_str:
            return len(value_as_str.split(".")[1])
        elif "e" in value_as_str:
            return abs(int(value_as_str.split("e")[1]))
    return 2
