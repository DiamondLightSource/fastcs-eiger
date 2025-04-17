import pytest
from pytest_mock import MockerFixture

from fastcs_eiger.eiger_controller import EigerHandler


@pytest.mark.asyncio
async def test_eiger_controller_creates_subcontrollers(
    mocker: MockerFixture, mock_connection
):
    eiger_controller, connection = mock_connection
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
    attr = mocker.Mock()

    controller.connection.get.return_value = {"value": 5}

    await updater.update(controller, attr)
    attr.set.assert_called_once_with(5)


@pytest.mark.asyncio
async def test_eiger_handler_put(mocker: MockerFixture):
    dummy_uri = "subsystem/api/1.8.0/dummy_mode/dummy_uri"
    controller = mocker.AsyncMock()
    await EigerHandler(dummy_uri).put(controller, mocker.Mock(), 0.1)
    controller.connection.put.assert_awaited_once_with(dummy_uri, 0.1)
    controller.queue_update.assert_awaited_once_with(
        list(controller.connection.put.return_value)
    )

    # if controller.connection.put returns [],
    # still queue_update for the handled uri
    controller.connection.put.return_value = []
    no_updated_params_uri = "susbsystem/api/1.8.0/dummy_mode/no_updated_params"
    await EigerHandler(no_updated_params_uri).put(controller, mocker.Mock(), 0.1)
    controller.connection.put.assert_awaited_with(no_updated_params_uri, 0.1)
    controller.queue_update.assert_awaited_with(["no_updated_params"])
