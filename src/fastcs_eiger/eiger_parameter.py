from dataclasses import dataclass
from typing import Any, Literal

from fastcs2 import DataType
from pydantic import BaseModel

# Keys to be ignored when introspecting the detector to create parameters
IGNORED_KEYS = [
    # Big arrays
    "countrate_correction_table",
    "pixel_mask",
    "threshold/1/pixel_mask",
    "threshold/2/pixel_mask",
    "flatfield",
    "threshold/1/flatfield",
    "threshold/2/flatfield",
    # Deprecated
    "board_000/th0_humidity",
    "board_000/th0_temp",
    # TODO: Value is [value, max], rather than using max metadata
    "buffer_fill_level",
    # TODO: Handle array values
    "detector_orientation",
    "detector_translation",
    # TODO: Is it a bad idea to include these?
    "test_image_mode",
    "test_image_value",
]

# Parameters that are in the API but missing from keys
MISSING_KEYS: dict[str, dict[str, list[str]]] = {
    "detector": {"status": ["error"], "config": ["wavelength"]},
    "monitor": {"status": [], "config": []},
    "stream": {"status": ["error"], "config": []},
}

FETCH_BEFORE_RETURNING = {"bit_depth_image", "bit_depth_readout"}


class EigerParameterResponse(BaseModel):
    access_mode: Literal["r", "w", "rw"]
    allowed_values: Any | None = None
    min: float | int | None = None
    value: Any
    value_type: Literal[
        "float", "int", "bool", "uint", "string", "datetime", "State", "string[]"
    ]


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

    @property
    def fastcs_datatype(self) -> type[DataType]:
        match self.response.value_type:
            case "float":
                return float
            case "int" | "uint":
                return int
            case "bool":
                return bool
            case "string" | "datetime" | "State" | "string[]":
                return str


EIGER_PARAMETER_SUBSYSTEMS = EigerParameter.__annotations__["subsystem"].__args__
EIGER_PARAMETER_MODES = EigerParameter.__annotations__["mode"].__args__


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
