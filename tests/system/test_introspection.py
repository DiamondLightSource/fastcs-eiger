import json
import os
import signal
import subprocess
from pathlib import Path
from time import sleep
from typing import Any

import pytest
from fastcs.attributes import AttrR
from fastcs.datatypes import Float

from fastcs_eiger.eiger_controller import (
    EigerController,
    EigerDetectorController,
    EigerParameter,
    EigerSubsystemController,
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


@pytest.fixture
def eiger_controller():
    yield EigerController("i04-1-eiger01", 80)


# Stolen from tickit-devices
# https://docs.pytest.org/en/latest/example/parametrize.html#indirect-parametrization
@pytest.fixture
def sim_eiger_controller(request):
    """Subprocess that runs ``tickit all <config_path>``."""
    config_path: str = request.param
    proc = subprocess.Popen(
        ["tickit", "all", config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait until ready
    while True:
        line = proc.stdout.readline()
        if "Starting HTTP server..." in line:
            break

    sleep(3)

    yield EigerController("127.0.0.1", 8081)

    proc.send_signal(signal.SIGINT)
    print(proc.communicate()[0])


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
        subsystem_parameters["DETECTOR"]
    )
    assert len(detector_attributes) == 76
    monitor_attributes = EigerSubsystemController._create_attributes(
        subsystem_parameters["MONITOR"]
    )
    assert len(monitor_attributes) == 7
    stream_attributes = EigerSubsystemController._create_attributes(
        subsystem_parameters["STREAM"]
    )
    assert len(stream_attributes) == 8

    assert isinstance(detector_attributes["humidity"], AttrR)
    assert isinstance(detector_attributes["humidity"].datatype, Float)
    assert detector_attributes["humidity"]._group == "DetectorStatus"
    assert detector_attributes["threshold_2_energy"]._group == "Threshold2"
    assert detector_attributes["threshold_energy"]._group == "Threshold"

    await controller.connection.close()
