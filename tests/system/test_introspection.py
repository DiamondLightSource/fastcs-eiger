import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastcs.attributes import AttrR
from fastcs.datatypes import Float

from fastcs_eiger.eiger_controller import (
    EigerController,
    EigerDetectorController,
    EigerMonitorController,
    EigerParameter,
    EigerStreamController,
)

HERE = Path(__file__).parent


def _serialise_parameter(parameter: EigerParameter) -> dict:
    return {
        "subsystem": parameter.subsystem,
        "mode": parameter.mode,
        "key": parameter.key,
        "response": {
            k: v
            for k, v in parameter.response.items()
            if k not in ("max", "min", "unit", "value")
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sim_eiger_controller", [str(HERE / "eiger.yaml")], indirect=True
)
async def test_introspection(sim_eiger_controller: EigerController):
    controller = sim_eiger_controller
    await controller.initialise()
    serialised_parameters: dict[str, dict[str, Any]] = {}
    subsystem_parameters = {}
    for subsystem_name, subcontroller in controller.get_sub_controllers().items():
        serialised_parameters[subsystem_name] = {}
        subsystem_parameters[
            subsystem_name
        ] = await subcontroller._introspect_detector_subsystem()
        for param in subsystem_parameters[subsystem_name]:
            serialised_parameters[subsystem_name][param.key] = _serialise_parameter(
                param
            )

    expected_file = HERE / "parameters.json"
    if os.environ.get("REGENERATE_TEST_OUTPUT", None):
        expected_file.write_text(json.dumps(serialised_parameters, indent=4))

    expected_parameters = json.loads(expected_file.read_text())

    assert serialised_parameters == expected_parameters, "Detector API does not match"

    detector_attributes = EigerDetectorController._create_attributes(
        subsystem_parameters["Detector"]
    )
    assert len(detector_attributes) == 76
    monitor_attributes = EigerMonitorController._create_attributes(
        subsystem_parameters["Monitor"]
    )
    assert len(monitor_attributes) == 7
    stream_attributes = EigerStreamController._create_attributes(
        subsystem_parameters["Stream"]
    )
    assert len(stream_attributes) == 8

    assert isinstance(detector_attributes["humidity"], AttrR)
    assert isinstance(detector_attributes["humidity"].datatype, Float)
    assert detector_attributes["humidity"]._group == "DetectorStatus"
    assert detector_attributes["threshold_2_energy"]._group == "Threshold2"
    assert (
        detector_attributes["threshold_difference_lower_threshold"]._group
        == "ThresholdDifference"
    )

    await controller.connection.close()
