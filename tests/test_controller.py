import pytest
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import EigerHandler, EigerSubsystemController


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
    assert list(eiger_controller.get_sub_controllers().keys()) == [
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
async def test_eiger_handler_update_updates_value(mocker: MockerFixture):
    dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    updater = EigerHandler(dummy_uri)
    controller = mocker.AsyncMock()
    mock_connection = mocker.AsyncMock()
    mock_connection.get.return_value = {"value": 5}
    controller = EigerSubsystemController(mock_connection, mocker.MagicMock())
    attr = mocker.Mock()

    await updater.initialise(controller)
    await updater.update(attr)
    attr.set.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_eiger_handler_put(mocker: MockerFixture):
    dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    mock_connection = mocker.AsyncMock()
    controller = EigerSubsystemController(mock_connection, mocker.AsyncMock())
    controller.queue_update = mocker.AsyncMock()

    handler = EigerHandler(dummy_uri)
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
    handler = EigerHandler(no_updated_params_uri)
    await handler.initialise(controller)
    await handler.put(mocker.Mock(), 0.1)
    mock_connection.put.assert_awaited_with(no_updated_params_uri, 0.1)
    controller.queue_update.assert_awaited_with(["no_updated_params"])
