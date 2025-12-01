import pytest
from fastcs.connections import IPConnectionSettings
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_odin_controller import EigerOdinController
from fastcs_eiger.odin.odin_controller import OdinController


@pytest.mark.asyncio
async def test_eiger_odin_controller(mocker: MockerFixture):
    detector_connection_settings = IPConnectionSettings("127.0.0.1", 8000)
    odin_connection_settings = IPConnectionSettings("127.0.0.1", 8001)

    controller = EigerOdinController(
        detector_connection_settings, odin_connection_settings
    )
    assert isinstance(controller.OD, OdinController)

    eiger_initialise_mock = mocker.patch(
        "fastcs_eiger.eiger_controller.EigerController.initialise"
    )
    odin_initialise_mock = mocker.patch.object(controller.OD, "initialise")

    await controller.initialise()

    eiger_initialise_mock.assert_called_once_with()
    odin_initialise_mock.assert_called_once_with()
