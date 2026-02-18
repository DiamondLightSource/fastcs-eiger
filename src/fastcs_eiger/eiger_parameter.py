from dataclasses import dataclass
from typing import Any, Literal

from fastcs.attributes import AttributeIORef
from fastcs.datatypes import Bool, DataType, Float, Int, String
from pydantic import BaseModel

EigerAPIVersion = Literal["1.6.0", "1.8.0"]


class EigerParameterResponse(BaseModel):
    access_mode: Literal["r", "w", "rw"] | None = None
    allowed_values: Any | None = None
    min: float | int | None = None
    value: Any
    value_type: Literal[
        "float", "int", "bool", "uint", "string", "datetime", "State", "string[]"
    ]


@dataclass(kw_only=True)
class EigerParameterRef(AttributeIORef):
    """IO ref for a parameter in the Eiger SIMPLON API"""

    update_period: float | None = 0.2
    """Poll period for parameter"""
    key: str
    """Last section of URI within a subsystem/mode."""
    subsystem: Literal["detector", "stream", "monitor"]
    """Subsystem within detector API."""
    api_version: EigerAPIVersion = "1.8.0"
    """Version of API to use."""
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
        return f"{self.subsystem}/api/{self.api_version}/{self.mode}/{self.key}"

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

    @property
    def response_access_mode(self) -> Literal["r", "w", "rw"] | None:
        if self.response.access_mode is None:
            if self.mode == "status":
                return "r"
            elif self.mode == "config":
                return "rw"
        else:
            return self.response.access_mode

    def __repr__(self):
        name = self.__class__.__name__
        return f"{name}(subsystem={self.subsystem}, mode={self.mode}, key={self.key})"


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
