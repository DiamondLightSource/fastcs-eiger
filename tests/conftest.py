import signal
import subprocess
from time import sleep
from unittest import mock

import pytest
from fastcs.connections import IPConnectionSettings
from pytest_mock import MockerFixture

from fastcs_eiger.controllers.eiger_controller import EigerController


# Stolen from tickit-devices
# https://docs.pytest.org/en/latest/example/parametrize.html#indirect-parametrization
@pytest.fixture(scope="session")
def sim_eiger(request):
    """Subprocess that runs ``tickit all <config_path>``."""
    config_path: str = request.param
    proc = subprocess.Popen(
        ["tickit", "all", config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait until ready
    while proc.stdout is not None:
        line = proc.stdout.readline()
        if "Starting HTTP server..." in line:
            break

    sleep(3)

    yield

    proc.send_signal(signal.SIGINT)
    print(proc.communicate()[0])


@pytest.fixture
def mock_connection(mocker: MockerFixture):
    eiger_controller = EigerController(
        IPConnectionSettings("127.0.0.1", 80), api_version="1.8.0"
    )
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get = mock.AsyncMock()
    connection.put = mock.AsyncMock()
    return eiger_controller, connection
