import signal
import subprocess
from pathlib import Path
from time import sleep

import pytest

from fastcs_eiger.eiger_controller import EigerController

HERE = Path(__file__).parent


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
