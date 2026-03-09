from pathlib import Path

import pytest
from fastcs.attributes import AttrR, AttrRW
from fastcs.connections import IPConnectionSettings
from fastcs.datatypes import Int, String
from pytest_mock import MockerFixture

from fastcs_eiger.controllers.eiger_controller import EigerController
from fastcs_eiger.controllers.odin.eiger_odin_controller import EigerOdinController
from fastcs_eiger.controllers.odin.odin_controller import OdinController


@pytest.fixture
def eiger_odin_controller(mocker: MockerFixture):
    detector_connection_settings = IPConnectionSettings("127.0.0.1", 8000)
    odin_connection_settings = IPConnectionSettings("127.0.0.1", 8001)
    controller = EigerOdinController(
        detector_connection_settings, odin_connection_settings, api_version="1.8.0"
    )

    controller.OD.file_path = AttrRW(String(), initial_value="/tmp/data")  # pyright: ignore[reportAttributeAccessIssue]
    controller.OD.file_prefix = AttrRW(String(), initial_value="test_prefix")  # pyright: ignore[reportAttributeAccessIssue]
    controller.OD.block_size = AttrRW(Int(), initial_value=4)  # pyright: ignore[reportAttributeAccessIssue]

    fp_mock = mocker.patch.object(controller.OD, "FP", create=True)
    fp_mock.data_compression.put = mocker.AsyncMock()
    fp_mock.data_datatype.put = mocker.AsyncMock()
    fp_mock.data_datatype.get.return_value = "uint16"
    fp_mock.frames = AttrRW(Int(), initial_value=100)
    fp_mock.process_blocks_per_file = AttrR(Int(), initial_value=10)
    fp_mock.data_dims_0 = AttrR(Int(), initial_value=512)
    fp_mock.data_dims_1 = AttrR(Int(), initial_value=1024)
    fp_mock.start_writing = mocker.AsyncMock()

    return controller


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

    create_mock = mocker.patch(
        "fastcs_eiger.controllers.odin.eiger_odin_controller.create_interleave_vds"
    )

    writing_wait_mock = mocker.patch.object(controller.OD.writing, "wait_for_value")

    writing_wait_mock.side_effect = TimeoutError
    with pytest.raises(TimeoutError, match="File writers failed to start"):
        await controller.start_writing()

    writing_wait_mock.side_effect = None
    await controller.start_writing()

    controller.OD.FP.data_compression.put.assert_awaited_with("LZ4")
    controller.OD.FP.data_datatype.put.assert_awaited_with("uint16")
    controller.OD.FP.start_writing.assert_awaited_with()
    writing_wait_mock.assert_awaited_with(
        True, timeout=controller.start_writing_timeout.get()
    )

    create_mock.assert_not_called()

    controller.enable_vds_creation._value = True
    await controller.start_writing()

    create_mock.assert_called_once_with(
        path=Path("/tmp/data"),
        prefix="test_prefix",
        datasets=["data", "data2", "data3"],
        frame_count=100,
        frames_per_block=4,
        blocks_per_file=10,
        frame_shape=(1024, 512),
        dtype="uint16",
    )
