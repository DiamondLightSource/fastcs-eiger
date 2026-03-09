import pytest
from fastcs.connections import IPConnectionSettings
from pytest_mock import MockerFixture

from fastcs_eiger.controllers.eiger_controller import EigerController
from fastcs_eiger.controllers.odin.eiger_odin_controller import EigerOdinController
from fastcs_eiger.controllers.odin.odin_controller import OdinController


@pytest.fixture
def eiger_odin_controller():
    detector_connection_settings = IPConnectionSettings("127.0.0.1", 8000)
    odin_connection_settings = IPConnectionSettings("127.0.0.1", 8001)
    return EigerOdinController(
        detector_connection_settings, odin_connection_settings, api_version="1.8.0"
    )


@pytest.mark.asyncio
async def test_eiger_odin_controller(eiger_odin_controller, mocker: MockerFixture):
    controller = eiger_odin_controller
    assert isinstance(controller.OD, OdinController)

    eiger_initialise_mock = mocker.patch(
        "fastcs_eiger.controllers.eiger_controller.EigerController.initialise"
    )
    odin_initialise_mock = mocker.patch.object(controller.OD, "initialise")

    await controller.initialise()

    eiger_initialise_mock.assert_called_once_with()
    odin_initialise_mock.assert_called_once_with()


@pytest.mark.asyncio
async def test_odin_arm_when_ready(eiger_odin_controller, mocker: MockerFixture):
    controller = eiger_odin_controller

    _super_arm_mock = mocker.patch.object(EigerController, "arm_when_ready")
    ef_mock = mocker.patch.object(controller.OD, "EF", create=True)
    ef_mock.ready.wait_for_value = mocker.AsyncMock()

    ef_mock.ready.wait_for_value.side_effect = TimeoutError
    with pytest.raises(TimeoutError, match="Eiger fan not ready"):
        await controller.arm_when_ready()

    _super_arm_mock.assert_called_once_with()

    ef_mock.ready.wait_for_value.side_effect = None
    await controller.arm_when_ready()


@pytest.mark.asyncio
async def test_start_writing(eiger_odin_controller, mocker: MockerFixture):
    controller = eiger_odin_controller

    detector_mock = mocker.patch.object(controller, "detector", create=True)
    detector_mock.compression.get.return_value = "lz4"
    detector_mock.bit_depth_image.get.return_value = 16

    fp_mock = mocker.patch.object(controller.OD, "FP", create=True)
    fp_mock.data_compression.put = mocker.AsyncMock()
    fp_mock.data_datatype.put = mocker.AsyncMock()
    fp_mock.start_writing = mocker.AsyncMock()

    writing_wait_mock = mocker.patch.object(controller.OD.writing, "wait_for_value")

    writing_wait_mock.side_effect = TimeoutError
    with pytest.raises(TimeoutError, match="File writers failed to start"):
        await controller.start_writing()

    writing_wait_mock.side_effect = None
    await controller.start_writing()

    fp_mock.data_compression.put.assert_awaited_with("LZ4")
    fp_mock.data_datatype.put.assert_awaited_with("uint16")
    fp_mock.start_writing.assert_awaited_with()
    writing_wait_mock.assert_awaited_with(
        True, timeout=controller.start_writing_timeout.get()
    )
