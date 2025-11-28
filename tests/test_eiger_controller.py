import pytest
from fastcs.attributes import AttrRW
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_detector_controller import EigerDetectorController
from fastcs_eiger.eiger_parameter import EigerParameterRef, EigerParameterResponse


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


@pytest.fixture
def subsystem_controller_and_connection(mock_connection):
    controller, connection = mock_connection
    subsystem_controller = EigerDetectorController(
        connection, controller.queue_subsystem_update
    )
    ref = EigerParameterRef(
        key="dummy_uri",
        subsystem="detector",
        mode="config",
        response=EigerParameterResponse(
            access_mode="rw", value=0.0, value_type="float"
        ),
    )
    subsystem_controller.dummy_attr = AttrRW(ref.fastcs_datatype, io_ref=ref)
    return subsystem_controller, connection


@pytest.mark.asyncio
async def test_eiger_io_update_updates_value(
    subsystem_controller_and_connection, mocker: MockerFixture
):
    subsystem_controller, connection = subsystem_controller_and_connection
    connection.get.return_value = {"value": 0.5}

    attr_update_spy = mocker.spy(subsystem_controller.dummy_attr, "update")

    await subsystem_controller._io.update(subsystem_controller.dummy_attr)
    attr_update_spy.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_eiger_io_send(
    subsystem_controller_and_connection, mocker: MockerFixture
):
    dummy_uri = "detector/api/1.8.0/config/dummy_uri"
    subsystem_controller, connection = subsystem_controller_and_connection

    io = subsystem_controller._io
    io.queue_update = mocker.AsyncMock()
    await io.send(subsystem_controller.dummy_attr, 0.1)

    connection.put.assert_awaited_once_with(dummy_uri, 0.1)
    io.queue_update.assert_awaited_once_with(list(connection.put.return_value))

    # if controller.connection.put returns [],
    # still queue_update for the handled uri
    ref = EigerParameterRef(
        key="no_updated_params",
        subsystem="detector",
        mode="config",
        response=EigerParameterResponse(
            access_mode="rw", value=0.0, value_type="float"
        ),
    )
    subsystem_controller.no_updated_params = AttrRW(ref.fastcs_datatype, io_ref=ref)

    connection.put.return_value = []
    no_updated_params_uri = "detector/api/1.8.0/config/no_updated_params"
    await io.send(subsystem_controller.no_updated_params, 0.1)
    connection.put.assert_awaited_with(no_updated_params_uri, 0.1)
    io.queue_update.assert_awaited_with(["no_updated_params"])
