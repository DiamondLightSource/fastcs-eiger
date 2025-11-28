import os
import signal
import subprocess
from time import sleep
from typing import Any
from unittest import mock

import pytest
from fastcs.connections import IPConnectionSettings
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import EigerController

# Prevent pytest from catching exceptions when debugging in vscode so that break on
# exception works correctly (see: https://github.com/pytest-dev/pytest/issues/7409)
if os.getenv("PYTEST_RAISE", "0") == "1":

    @pytest.hookimpl(tryfirst=True)
    def pytest_exception_interact(call: pytest.CallInfo[Any]):
        if call.excinfo is not None:
            raise call.excinfo.value
        else:
            raise RuntimeError(
                f"{call} has no exception data, an unknown error has occurred"
            )

    @pytest.hookimpl(tryfirst=True)
    def pytest_internalerror(excinfo: pytest.ExceptionInfo[Any]):
        raise excinfo.value


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
    while proc.stdout is not None:
        line = proc.stdout.readline()
        if "Starting HTTP server..." in line:
            break

    sleep(3)

    yield EigerController(IPConnectionSettings("127.0.0.1", 8081))

    proc.send_signal(signal.SIGINT)
    print(proc.communicate()[0])


@pytest.fixture
def mock_connection(mocker: MockerFixture):
    eiger_controller = EigerController(IPConnectionSettings("127.0.0.1", 80))
    connection = mocker.patch.object(eiger_controller, "connection")
    connection.get = mock.AsyncMock()
    connection.put = mock.AsyncMock()
    return eiger_controller, connection
