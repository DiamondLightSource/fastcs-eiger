import json
import os
import signal
import subprocess
from pathlib import Path
from time import sleep

import pytest
from fastcs.attributes import AttrR
from fastcs.datatypes import Float

from fastcs_eiger.eiger_controller import EigerController, EigerParameter

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
    # controller = eiger_controller

    controller.connection.open()
    _parameters = await controller._introspect_detector()
    controller._tag_key_clashes(_parameters)
    parameters = {p.name: _serialise_parameter(p) for p in _parameters}

    expected_file = HERE / "parameters.json"
    if os.environ.get("REGENERATE_TEST_OUTPUT", None):
        expected_file.write_text(json.dumps(parameters, indent=4))

    expected_parameters = json.loads(expected_file.read_text())

    assert parameters == expected_parameters, "Detector API does not match"

    attributes = controller._create_attributes(_parameters)

    assert len(attributes) == 91
    assert isinstance(attributes["humidity"], AttrR)
    assert isinstance(attributes["humidity"].datatype, Float)
    assert attributes["humidity"]._group == "DetectorStatus"

    await controller.connection.close()
