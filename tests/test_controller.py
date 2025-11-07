import pytest
from fastcs.attributes import AttrRW
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import (
    EigerDetectorController,
    EigerSubsystemController,
)
from fastcs_eiger.eiger_parameter import EigerParameterRef, EigerParameterResponse
from fastcs_eiger.io import EigerAttributeIO


@pytest.mark.asyncio
async def test_eiger_controller_creates_subcontrollers(mock_connection):
    eiger_controller, connection = mock_connection

    # Arbitrary HTTP response for pydantic model.
    connection.get.return_value = {
        "access_mode": "r",
        "allowed_values": None,
        "value": "test_value",
        "value_type": "string",
    }

    await eiger_controller.initialise()
    assert list(eiger_controller.sub_controllers.keys()) == [
        "Detector",
        "Stream",
        "Monitor",
    ]
    connection.get.assert_any_call("detector/api/1.8.0/status/state")
    connection.get.assert_any_call("detector/api/1.8.0/status/keys")
    connection.get.assert_any_call("detector/api/1.8.0/config/keys")
    connection.get.assert_any_call("monitor/api/1.8.0/status/keys")
    connection.get.assert_any_call("monitor/api/1.8.0/config/keys")
    connection.get.assert_any_call("stream/api/1.8.0/status/keys")
    connection.get.assert_any_call("stream/api/1.8.0/config/keys")


@pytest.mark.asyncio
async def test_eiger_io_update_updates_value(mock_connection, mocker: MockerFixture):
    # dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    controller, connection = mock_connection
    connection.get.return_value = {"value": 5}
    # await controller.initialise()
    subsystem_controller = EigerDetectorController(
        connection, controller.queue_subsystem_update
    )
    io = subsystem_controller._io
    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        mode="config",
        response=EigerParameterResponse(access_mode="r", value=1, value_type="int"),
    )
    subsystem_controller.dummy_attr = AttrRW(ref.fastcs_datatype, io_ref=ref)
    attr_update_spy = mocker.spy(subsystem_controller.dummy_attr, "update")

    await io.update(subsystem_controller.dummy_attr)
    attr_update_spy.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_eiger_handler_put(mocker: MockerFixture):
    dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    mock_connection = mocker.AsyncMock()
    controller = EigerSubsystemController(mock_connection, mocker.AsyncMock())
    controller.queue_update = mocker.AsyncMock()

    handler = EigerAttributeIO(dummy_uri)
    await handler.initialise(controller)
    await handler.put(mocker.Mock(), 0.1)

    mock_connection.put.assert_awaited_once_with(dummy_uri, 0.1)
    controller.queue_update.assert_awaited_once_with(
        list(mock_connection.put.return_value)
    )

    # if controller.connection.put returns [],
    # still queue_update for the handled uri
    mock_connection.put.return_value = []
    no_updated_params_uri = "susbsystem/api/1.8.0/dummy_mode/no_updated_params"
    handler = EigerAttributeIO(no_updated_params_uri)
    await handler.initialise(controller)
    await handler.put(mocker.Mock(), 0.1)
    mock_connection.put.assert_awaited_with(no_updated_params_uri, 0.1)
    controller.queue_update.assert_awaited_with(["no_updated_params"])
