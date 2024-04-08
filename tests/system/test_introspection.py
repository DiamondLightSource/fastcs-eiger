import json
import os
import signal
import subprocess
from pathlib import Path
from time import sleep

import pytest

from eiger_fastcs.eiger_controller import EigerController, EigerParameter

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


@pytest.fixture
def sim_eiger_controller():
    cmd = ["tickit", "all", str(HERE / "eiger.yaml")]
    sim = subprocess.Popen(cmd)

    sleep(3)

    yield EigerController("127.0.0.1", 8081)

    sim.send_signal(signal.SIGTERM)
    sleep(0.1)
    sim.kill()


@pytest.mark.asyncio
async def test_introspection(sim_eiger_controller: EigerController):
    controller = sim_eiger_controller
    # controller = eiger_controller

    await controller.connect()
    _parameters = await controller._introspect_detector()
    controller._tag_key_clashes(_parameters)
    parameters = {p.name: _serialise_parameter(p) for p in _parameters}

    expected_file = HERE / "parameters.json"
    if os.environ.get("REGENERATE_TEST_OUTPUT", None):
        expected_file.write_text(json.dumps(parameters, indent=4))

    expected_parameters = json.loads(expected_file.read_text())

    assert parameters == expected_parameters, "Detector API does not match"

    await controller.close()
